"""Tests for the repository factory's runtime selection + local fallback."""
import pytest

from advocate.data.repository import InMemoryPipelineRepository
from advocate.data.repository_factory import get_repository, reset_cache


@pytest.fixture(autouse=True)
def _clear_cache(monkeypatch):
    reset_cache()
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    yield
    reset_cache()


def test_falls_back_to_in_memory_without_project():
    repo = get_repository()
    assert isinstance(repo, InMemoryPipelineRepository)


def test_force_memory_bypasses_cache_and_project(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "some-project")
    repo = get_repository(force_memory=True)
    assert isinstance(repo, InMemoryPipelineRepository)


def test_caches_repository_instance():
    a = get_repository()
    b = get_repository()
    assert a is b
