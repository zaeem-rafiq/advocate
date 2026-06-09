"""Deterministic NL→intent router for the Advocate command line. Pure, stdlib-only, no Gradio.

This is intentionally NOT an LLM. Routing a short command to a step or a prefilled brief is
keyword + preposition slot-extraction — instant, free, and deterministic (same input → same
output), which is exactly what `latent vs. deterministic` calls for. The parser only ever
*classifies* intent; it never fires a grounded (cost-bearing) call. The Gradio handler that
consumes these intents navigates + prefills only — the user clicks the step's own CTA to spend,
so a typed command can never silently run a grounded search/draft/prep (confirm-before-fire).

Grammar (see `command_help`):
  navigate     rate | rank | outreach | prep | "go to source" | "show 3b7" …
  set brief    "find {function} in {industry} near {place}"   (fills the brief; you click Find)
  prep         "prep {company}"
  draft        "draft to {contact}"
  help         help | ? | commands
"""
from __future__ import annotations

import re
from typing import Optional

# Step key → index mirrors advocate/ui/steps.py STEPS order (kept as plain ints so this module
# stays Gradio/step-model free and trivially unit-testable). Multiword aliases are matched whole.
_STEP_ALIASES = {
    "connect": 0, "brief": 0,
    "source": 1, "sourcing": 1, "employers": 1, "find": 1, "search": 1,
    "rate": 2, "rating": 2, "ratings": 2,
    "rank": 3, "ranking": 3, "active five": 3, "active 5": 3,
    "outreach": 4, "email": 4, "note": 4, "draft": 4, "write": 4, "reach out": 4,
    "3b7": 5, "cadence": 5, "follow up": 5, "follow-up": 5, "followup": 5, "follow ups": 5,
    "prep": 6, "tiara": 6, "interview": 6, "prepare": 6, "research": 6,
}

# Leading phrases people prefix a navigation with ("go to rate", "show me prep").
_GO_PREFIX = re.compile(r"^(?:go to|go|show me|show|open|take me to|navigate to|jump to)\s+")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def parse_command(text: str) -> dict:
    """Classify a typed command into a structured intent. Never raises; unknown → {kind:'unknown'}.

    kinds: noop | help | nav{step} | source{function,industry,geography} | prep{company}
           | draft{company} | unknown{text}
    """
    raw = _clean(text)
    if not raw:
        return {"kind": "noop"}
    t = raw.lower()  # same length/indices as raw → object slices below preserve original case
    if t in ("help", "?", "/help", "commands", "/commands"):
        return {"kind": "help"}

    # verb + OBJECT → action intents. A bare verb (no object) falls through to navigation, so
    # "prep" navigates to the Prep step while "prep Patagonia" prepares that company.
    m = re.match(r"^(?:find|source|search)\s+(.+)$", t)
    if m:
        return _parse_source(raw[m.start(1):])
    m = re.match(r"^(?:prep|prepare|research)\s+(?:for\s+|the\s+)?(.+)$", t)
    if m:
        return {"kind": "prep", "company": _clean(raw[m.start(1):])}
    m = re.match(r"^(?:draft|write|reach out)\s+(?:to\s+|a note to\s+)?(.+)$", t)
    if m:
        return {"kind": "draft", "company": _clean(raw[m.start(1):])}

    step = _parse_nav(t)
    if step is not None:
        return {"kind": "nav", "step": step}
    return {"kind": "unknown", "text": raw}


def _parse_source(rest: str) -> dict:
    """Slot-extract a brief from the words after find/source/search.

    Anchors: geography follows ' near '/' around '; industry follows ' in '; the head is the
    function. Missing slots come back empty — _on_source's own validation asks for the rest, and
    nothing is spent until the user clicks Find.
    """
    rest = _clean(rest)
    low = rest.lower()
    geography = ""
    g = re.search(r"\s+(?:near|around)\s+(.+)$", low)
    if g:
        geography = _clean(rest[g.start(1):])
        rest = _clean(rest[:g.start()])
        low = rest.lower()
    function, industry = rest, ""
    inm = re.search(r"\s+in\s+(.+)$", low)
    if inm:
        industry = _clean(rest[inm.start(1):])
        function = _clean(rest[:inm.start()])
    return {"kind": "source", "function": function, "industry": industry, "geography": geography}


def _parse_nav(t: str) -> Optional[int]:
    """Map a navigation phrase (or bare step word) to a step index, or None if it isn't one."""
    stripped = _GO_PREFIX.sub("", t).strip()
    return _STEP_ALIASES.get(stripped)


def command_help() -> str:
    """Terse one-line help for `help`/`?` — kept to a single block so it stays compact under the
    command line (a multi-paragraph dump would overflow the viewport-tight steps)."""
    return (
        "**Commands** — I navigate & prefill; *you* click to spend. "
        "`rate` · `rank` · `prep` to navigate · `find product management in climate near NYC` to set "
        "your brief · `prep Patagonia` · `draft to Maya`."
    )
