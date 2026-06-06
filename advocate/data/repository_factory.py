"""Selects the pipeline repository for the current runtime.

On Cloud Run (GOOGLE_CLOUD_PROJECT set) we use durable Firestore; locally we fall
back to the in-memory repository so development and tests need no cloud. The chosen
repository is cached so the Firestore client / in-memory store is reused per process.
"""
from __future__ import annotations

import os
from typing import Optional

from advocate.data.repository import InMemoryPipelineRepository, PipelineRepository

_cached: Optional[PipelineRepository] = None


def get_repository(force_memory: bool = False) -> PipelineRepository:
    """Return the process-wide repository (Firestore on Cloud Run, else in-memory)."""
    global _cached
    if _cached is not None and not force_memory:
        return _cached

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project and not force_memory:
        try:
            from advocate.data.firestore_repo import FirestorePipelineRepository

            _cached = FirestorePipelineRepository(project=project)
            return _cached
        except Exception:
            # Never crash the agent over storage init; degrade to in-memory.
            pass

    repo = InMemoryPipelineRepository()
    if not force_memory:
        _cached = repo
    return repo


def reset_cache() -> None:
    """Test hook: clear the cached repository."""
    global _cached
    _cached = None
