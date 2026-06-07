"""Grounding-source collection + inline citation rendering. Pure code.

Lifted from Google's Deep Search grounding callbacks
(`google/adk-samples` → `python/agents/deep-search/app/agent.py`, Apache-2.0):
`collect_research_sources_callback` builds confidence-scored `src-N` sources from a
response's grounding metadata, and `citation_replacement_callback` turns inline
`<cite source="src-N"/>` tags into Markdown links. Here they are rewritten as plain
functions that RETURN values instead of mutating `callback_context.state`, so the loop
in `prepare_informational` can thread sources explicitly and so this stays unit-testable
against duck-typed grounding-metadata fakes (no ADK / genai import in `core`).

The grounding-metadata shape is duck-typed (Gemini/Vertex `GroundingMetadata`): each
metadata has `.grounding_chunks` (chunk `.web.uri/.title/.domain`) and
`.grounding_supports` (`.confidence_scores`, `.grounding_chunk_indices`, `.segment.text`).
Anything missing is treated as "no grounding" — a thin source degrades honestly to zero
sources rather than raising.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Tuple

_LOG = logging.getLogger("advocate.citations")

# A source whose representative confidence is below this is flagged inline as weakly
# grounded — Advocate shows thin grounding rather than hiding it. (Also the default used
# for a support that cites a chunk without supplying a score, matching the sample.)
LOW_CONFIDENCE_THRESHOLD = 0.5

# Matches <cite source="src-N"/> and its spaced / single-quoted / unquoted variants.
# Lifted from citation_replacement_callback.
_CITE_RE = re.compile(r'<cite\s+source\s*=\s*["\']?\s*(src-\d+)\s*["\']?\s*/>')
# Collapse whitespace left before punctuation once a tag is replaced or dropped.
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.,;:])")


@dataclass(frozen=True)
class Source:
    """One grounded web source, with a representative confidence in [0, 1].

    `confidence` is the max confidence across the grounding supports that cite this
    source (0.0 if none did). `title` falls back to `domain` when the provider reports
    them equal, matching the Deep Search convention.
    """

    short_id: str
    title: str
    url: str
    domain: str
    confidence: float


def collect_sources(
    metadatas: Iterable[object],
    sources: Mapping[str, Source] | None = None,
    url_to_short_id: Mapping[str, str] | None = None,
) -> Tuple[Dict[str, Source], Dict[str, str]]:
    """Collect confidence-scored sources from grounding metadata.

    Assigns `src-N` ids (continuing from any `url_to_short_id` accumulator passed in),
    dedupes by URL, and records each source's representative confidence (the max over
    the grounding supports that reference it). Returns NEW ``(sources, url_to_short_id)``
    dicts — the inputs are never mutated, so a refine pass can merge new findings into
    the sources already collected without surprising its caller.
    """
    url_to_short_id_out: Dict[str, str] = dict(url_to_short_id or {})
    # Mutable working view so we can update a source's confidence before freezing it.
    working: Dict[str, dict] = {
        sid: {
            "short_id": s.short_id,
            "title": s.title,
            "url": s.url,
            "domain": s.domain,
            "confidence": s.confidence,
        }
        for sid, s in (sources or {}).items()
    }
    id_counter = len(url_to_short_id_out) + 1

    for metadata in metadatas:
        chunks = getattr(metadata, "grounding_chunks", None) or []
        chunk_idx_to_short_id: Dict[int, str] = {}
        for idx, chunk in enumerate(chunks):
            web = getattr(chunk, "web", None)
            if not web:
                continue
            url = getattr(web, "uri", None)
            if not url:
                continue
            domain = getattr(web, "domain", "") or ""
            raw_title = getattr(web, "title", None)
            title = raw_title if (raw_title and raw_title != domain) else domain
            title = title or url  # last resort when domain is also blank
            if url not in url_to_short_id_out:
                short_id = f"src-{id_counter}"
                url_to_short_id_out[url] = short_id
                working[short_id] = {
                    "short_id": short_id,
                    "title": title,
                    "url": url,
                    "domain": domain,
                    "confidence": 0.0,
                }
                id_counter += 1
            chunk_idx_to_short_id[idx] = url_to_short_id_out[url]

        supports = getattr(metadata, "grounding_supports", None) or []
        for support in supports:
            confidence_scores = getattr(support, "confidence_scores", None) or []
            chunk_indices = getattr(support, "grounding_chunk_indices", None) or []
            for i, chunk_idx in enumerate(chunk_indices):
                short_id = chunk_idx_to_short_id.get(chunk_idx)
                if short_id is None:
                    continue
                confidence = (
                    confidence_scores[i]
                    if i < len(confidence_scores)
                    else LOW_CONFIDENCE_THRESHOLD
                )
                working[short_id]["confidence"] = max(
                    working[short_id]["confidence"], confidence
                )

    frozen = {
        sid: Source(
            short_id=d["short_id"],
            title=d["title"],
            url=d["url"],
            domain=d["domain"],
            confidence=d["confidence"],
        )
        for sid, d in working.items()
    }
    return frozen, url_to_short_id_out


def grounding_used(metadatas: Iterable[object]) -> bool:
    """True if any grounding metadata shows the model actually ran a web search.

    For a PROSE reply, grounding attaches `grounding_chunks` / `grounding_supports`
    tied to text spans, and `collect_sources` turns those into citeable `src-N` sources.
    A STRUCTURED (JSON) reply has no text spans, so the provider emits zero chunks even
    though it searched — the proof of grounding is then `web_search_queries` (and a
    `search_entry_point`). This signal covers BOTH shapes, so a caller that does not
    render inline citations (e.g. sourcing, which returns a JSON org list) can tell a
    grounded reply from a fabricated one — where `collect_sources` alone would wrongly
    report "ungrounded". A thin reply with neither searches nor chunks returns False.
    """
    for metadata in metadatas:
        if getattr(metadata, "web_search_queries", None):
            return True
        if getattr(metadata, "grounding_chunks", None):
            return True
    return False


def replace_citations(
    report: str,
    sources: Mapping[str, Source],
    show_confidence: bool = True,
) -> str:
    """Replace inline `<cite source="src-N"/>` tags with Markdown links.

    A known source becomes ``[title](url)``; when ``show_confidence`` and the source is
    below ``LOW_CONFIDENCE_THRESHOLD`` it is annotated `` (low confidence)`` so weak
    grounding is visible. A tag whose source was never collected is dropped (and logged)
    rather than left dangling — pure code never surfaces a citation it can't back.
    """

    def _replace(match: "re.Match[str]") -> str:
        short_id = match.group(1)
        source = sources.get(short_id)
        if source is None:
            _LOG.warning("dropping citation to unknown source %s", short_id)
            return ""
        display = source.title or source.domain or short_id
        link = f" [{display}]({source.url})"
        if show_confidence and source.confidence < LOW_CONFIDENCE_THRESHOLD:
            link += " (low confidence)"
        return link

    processed = _CITE_RE.sub(_replace, report)
    processed = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", processed)
    return processed
