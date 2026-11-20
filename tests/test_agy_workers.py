"""Tests for AGY worker registry and profile/path resolution."""

from pathlib import Path

import pytest

from pab.providers.agy.workers import AgyWorkerRegistry, AgyWorkerResolutionError


@pytest.fixture
def registry(tmp_path: Path) -> AgyWorkerRegistry:
    workers = [
        {
            "id": "sales",
            "label": "AGY-Sales",
            "profile": "seekn",
            "workdir": str(tmp_path / "agents" / "sales"),
            "responsibility": "Leads",
        },
        {
            "id": "qa",
            "label": "AGY-QA",
            "profile": "ogui",
            "workdir": str(tmp_path / "agents" / "qa"),
            "responsibility": "Quality",
        },
    ]
    return AgyWorkerRegistry(workers=workers, worker_base=tmp_path, profile_root=tmp_path)


def test_resolve_by_worker_id(registry: AgyWorkerRegistry):
    worker = registry.resolve(worker_id="sales")
    assert worker.worker_id == "sales"
    assert worker.profile == "seekn"
    assert worker.profile_home.name == ".agy-seekn"


def test_resolve_by_absolute_worktree(registry: AgyWorkerRegistry, tmp_path: Path):
    worker = registry.resolve(worktree=tmp_path / "agents" / "qa")
    assert worker.worker_id == "qa"
    assert worker.profile == "ogui"


def test_resolve_by_mirrored_absolute_worktree(registry: AgyWorkerRegistry, tmp_path: Path):
    """An agent tree mirrored under another root still resolves to the right profile."""
    mirrored = tmp_path / "other" / "projects" / "sentinel_ops" / "agents" / "sales"
    worker = registry.resolve(worktree=mirrored)
    assert worker.worker_id == "sales"
    assert worker.profile == "seekn"


def test_resolve_unknown_worker_raises(registry: AgyWorkerRegistry, tmp_path: Path):
    with pytest.raises(AgyWorkerResolutionError) as exc:
        registry.resolve(worker_id="does-not-exist", worktree=tmp_path / "nowhere")
    assert "does-not-exist" in str(exc.value)


def test_resolve_unknown_worker_never_remaps(registry: AgyWorkerRegistry, tmp_path: Path):
    """An explicitly requested but unknown worker id is an error, never remapped."""
    with pytest.raises(AgyWorkerResolutionError) as exc:
        registry.resolve(worker_id="personaos-agy", worktree=tmp_path / "agents" / "sales")
    assert "personaos-agy" in str(exc.value)


def test_resolve_without_any_hint_raises(registry: AgyWorkerRegistry):
    with pytest.raises(AgyWorkerResolutionError):
        registry.resolve()


def test_resolve_unmatched_worktree_raises(registry: AgyWorkerRegistry, tmp_path: Path):
    with pytest.raises(AgyWorkerResolutionError):
        registry.resolve(worktree=tmp_path / "somewhere" / "else")


def test_default_registry_contains_five_workers():
    default = AgyWorkerRegistry()
    ids = {w.worker_id for w in default.list_workers()}
    assert ids == {"automation", "delivery", "qa", "research", "sales"}
    profiles = {w.worker_id: w.profile for w in default.list_workers()}
    assert profiles["sales"] == "seekn"
    assert profiles["research"] == "yk2012"
    assert profiles["delivery"] == "93975"
    assert profiles["automation"] == "cylyl"
    assert profiles["qa"] == "ogui"
