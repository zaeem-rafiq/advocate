"""Stash/recover the candidate list's authoritative ranking signals in ADK session state.

Between sourcing and ranking the orchestrator LLM re-serializes the org list to fold in
the user's motivation scores, and can drop `posting_score`/`has_alumni` — which the
rank/persist tools then silently default to 0/False, erasing the signals. To make the
signals authoritative, the producers (`source_organizations`, `load_seed_companies`)
stash them here keyed by company, and the consumers (`rank_companies`, `set_active_five`,
`save_pipeline`) recover them — taking only motivation + identity from the LLM.

`tool_context` is duck-typed (only `.state` is used), so this module needs no ADK import
and stays unit-testable with a tiny fake context. All access is best-effort: a missing
context or a state-read/write fault degrades to the LLM-provided values, never a crash.
"""
from __future__ import annotations

import logging
from typing import List, Mapping

from advocate.core.sourcing import CANDIDATE_SIGNALS_KEY, reconcile_signals, signals_index

_LOG = logging.getLogger("advocate.session_state")


def stash_candidate_signals(tool_context, companies: List[Mapping]) -> None:
    """Merge the candidate list's authoritative ranking signals into session state.

    Best-effort and additive (a later producer in the same session adds to, not replaces,
    what an earlier one stored). No-op when there is no session context.
    """
    if tool_context is None:
        return
    try:
        existing = dict(tool_context.state.get(CANDIDATE_SIGNALS_KEY, {}) or {})
        existing.update(signals_index(companies))
        tool_context.state[CANDIDATE_SIGNALS_KEY] = existing
    except Exception:  # noqa: BLE001 — observability lives elsewhere; never break the tool
        _LOG.warning("could not persist candidate signals to session state")


def recover_signals(tool_context, companies: List[Mapping]) -> List[dict]:
    """Reconcile posting_score/has_alumni from session state onto user-scored company dicts.

    Empty state or no context → the input's own values pass through unchanged (so paths
    that never stashed, and existing callers without a context, behave exactly as before).
    """
    authoritative: Mapping[str, Mapping] = {}
    if tool_context is not None:
        try:
            authoritative = tool_context.state.get(CANDIDATE_SIGNALS_KEY, {}) or {}
        except Exception:  # noqa: BLE001 — degrade to LLM-provided values
            authoritative = {}
    return reconcile_signals(companies, authoritative)
