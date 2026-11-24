"""Tests for AGY adapter launch() and PAB dispatch lifecycle (fake `agy` binary)."""

import json
import stat
from pathlib import Path

import pytest

from pab.core.config import ConfigManager
from pab.core.exceptions import UnsupportedOperationError
from pab.core.models.execution import ExecutionMode, ExecutionStatus, LaunchRequest
from pab.core.models.orchestration import DispatchStatus, TaskStatus
from pab.core.orchestration_engine import OrchestrationEngine
from pab.providers.agy.adapter import AgyAdapter
from pab.providers.agy.execution import AgyRunner
from pab.providers.agy.workers import AgyWorkerRegistry

FAKE_AGY = """#!/usr/bin/env bash
case "${FAKE_AGY_MODE:-success}" in
  success)
    echo '{"conversation_id":"conv-abc","status":"SUCCESS","response":"AGY says hello","num_turns":1,"usage":{"total_tokens":11}}'
    ;;
  fail)
    echo "agy failed hard" >&2
    exit 7
    ;;
esac
"""


@pytest.fixture
def fake_agy(tmp_path: Path) -> Path:
    script = tmp_path / "fake_agy.sh"
    script.write_text(FAKE_AGY, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


@pytest.fixture
def agy_env(tmp_path: Path, fake_agy: Path, monkeypatch):
    """Worker dir + profile home + registry/runner pointing at the fake binary."""
    workdir = tmp_path / "agents" / "sales"
    workdir.mkdir(parents=True)
    profile_home = tmp_path / ".agy-seekn"
    profile_home.mkdir()

    registry = AgyWorkerRegistry(
        workers=[
            {
                "id": "sales",
                "label": "AGY-Sales",
                "profile": "seekn",
                "workdir": str(workdir),
                "profile_home": str(profile_home),
            }
        ],
        worker_base=tmp_path,
        profile_root=tmp_path,
    )
    runner = AgyRunner(executable_path=str(fake_agy))
    adapter = AgyAdapter(worker_registry=registry, runner=runner)

    # Keep capability detection offline-fast and deterministic.
    monkeypatch.setattr(type(adapter), "version", lambda self: "test-version")
    monkeypatch.setenv("FAKE_AGY_LOG", str(tmp_path / "agy.log"))
    return {"adapter": adapter, "workdir": workdir, "profile_home": profile_home, "runner": runner}


def _launch_request(workdir: Path, worker_id: str = "sales") -> LaunchRequest:
    return LaunchRequest(
        request_id="req-1",
        idempotency_key="idem-1",
        worker_id=worker_id,
        task_id="task-1",
        provider="agy",
        workspace_path=workdir,
        prompt="say hello",
        execution_mode=ExecutionMode.MANAGED_PROCESS,
        timeout_seconds=60,
    )


# ---------------------------------------------------------------- adapter ----
def test_adapter_launch_returns_completed_handle(agy_env):
    adapter = agy_env["adapter"]
    handle = adapter.launch(_launch_request(agy_env["workdir"]))

    assert handle.status == ExecutionStatus.COMPLETED
    assert handle.exit_code == 0
    assert handle.native_session_id == "conv-abc"
    assert handle.error_message is None
    assert handle.metadata["profile"] == "seekn"
    assert handle.metadata["response"] == "AGY says hello"
    assert handle.metadata["conversation_id"] == "conv-abc"
    assert handle.metadata["workdir"] == str(agy_env["workdir"])


def test_adapter_launch_records_failure(agy_env, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "fail")
    adapter = agy_env["adapter"]
    handle = adapter.launch(_launch_request(agy_env["workdir"]))

    assert handle.status == ExecutionStatus.FAILED
    assert handle.exit_code == 7
    assert "non-zero" in (handle.error_message or "")
    assert handle.metadata["ok"] is False


def test_adapter_launch_rejects_unknown_worker(agy_env):
    adapter = agy_env["adapter"]
    with pytest.raises(Exception) as exc:
        adapter.launch(_launch_request(agy_env["workdir"], worker_id="not-a-worker"))
    assert "not-a-worker" in str(exc.value)


def test_adapter_inspect_returns_recorded_handle(agy_env):
    adapter = agy_env["adapter"]
    handle = adapter.launch(_launch_request(agy_env["workdir"]))
    assert adapter.inspect(handle.execution_id).execution_id == handle.execution_id


# ----------------------------------------------------------------- engine ----
@pytest.fixture
def engine(config_mgr: ConfigManager, agy_env) -> OrchestrationEngine:
    eng = OrchestrationEngine(config_mgr)
    eng.providers._providers["agy"] = agy_env["adapter"]
    return eng


def test_dispatch_to_agy_executes_and_completes_task(engine: OrchestrationEngine, agy_env, tmp_path: Path):
    run = engine.create_run(name="agy-run", objective="Run AGY", workspace_path=tmp_path)
    task = engine.create_task(run_id=run.run_id, title="Greet", spec="say hello", worker_id="sales")

    dispatch = engine.dispatch_task(
        run_id=run.run_id,
        task_id=task.task_id,
        agent_provider="agy",
        worker_id="sales",
    )

    assert dispatch.status == DispatchStatus.SETTLED
    assert dispatch.worktree_path == str(agy_env["workdir"])
    assert dispatch.metadata["conversation_id"] == "conv-abc"
    assert dispatch.metadata["profile"] == "seekn"
    assert "AGY says hello" in (dispatch.result_summary or "")

    # Task lifecycle: completed only because a real execution returned a valid result.
    assert engine.get_task(task.task_id).status == TaskStatus.COMPLETED


def test_dispatch_records_are_persisted_and_match_execution(engine: OrchestrationEngine, agy_env, tmp_path: Path):
    run = engine.create_run(name="agy-run", objective="Run AGY", workspace_path=tmp_path)
    task = engine.create_task(run_id=run.run_id, title="Greet", spec="say hello", worker_id="sales")

    dispatch = engine.dispatch_task(
        run_id=run.run_id,
        task_id=task.task_id,
        agent_provider="agy",
        worker_id="sales",
    )

    stored = engine.db.get_dispatch(dispatch.dispatch_id)
    assert stored is not None
    assert stored.status == DispatchStatus.SETTLED
    assert stored.metadata["conversation_id"] == "conv-abc"

    execution = engine.db.get_execution_by_idempotency_key(dispatch.metadata["execution_id"].replace("exec-", "idem-")) if False else None
    executions = engine.db.list_executions(provider="agy")
    assert len(executions) == 1
    assert executions[0].status == ExecutionStatus.COMPLETED
    assert executions[0].native_session_id == "conv-abc"
    assert executions[0].metadata["response"] == "AGY says hello"


def test_failed_agy_execution_marks_task_failed(engine: OrchestrationEngine, agy_env, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "fail")
    run = engine.create_run(name="agy-run", objective="Run AGY", workspace_path=tmp_path)
    task = engine.create_task(run_id=run.run_id, title="Greet", spec="say hello", worker_id="sales")

    dispatch = engine.dispatch_task(
        run_id=run.run_id,
        task_id=task.task_id,
        agent_provider="agy",
        worker_id="sales",
    )

    assert dispatch.status == DispatchStatus.FAILED
    assert engine.get_task(task.task_id).status == TaskStatus.FAILED
    assert "failed" in (dispatch.result_summary or "").lower()


def test_dispatch_to_unsupported_provider_fails_explicitly(engine: OrchestrationEngine, tmp_path: Path):
    run = engine.create_run(name="unsupported-run", objective="No fake success", workspace_path=tmp_path)
    task = engine.create_task(run_id=run.run_id, title="Review", spec="review the code")

    for provider in ("claude", "codex", "openclaw"):
        with pytest.raises(UnsupportedOperationError) as exc:
            engine.dispatch_task(
                run_id=run.run_id,
                task_id=task.task_id,
                agent_provider=provider,
            )
        assert provider in str(exc.value)

    # No dispatch was recorded and the task was not completed.
    assert engine.db.list_dispatches(run_id=run.run_id) == []
    assert engine.get_task(task.task_id).status == TaskStatus.PENDING


def test_absolute_worktree_is_used_verbatim(engine: OrchestrationEngine, agy_env, tmp_path: Path):
    run = engine.create_run(name="agy-run", objective="Run AGY", workspace_path=tmp_path / "run-ws")
    task = engine.create_task(run_id=run.run_id, title="Greet", spec="say hello", worker_id="sales")

    other = tmp_path / "elsewhere"
    other.mkdir()

    dispatch = engine.dispatch_task(
        run_id=run.run_id,
        task_id=task.task_id,
        agent_provider="agy",
        worker_id="sales",
        worktree_path=other,
    )

    assert dispatch.worktree_path == str(other)


def test_relative_worktree_resolves_against_run_workspace(engine: OrchestrationEngine, agy_env, tmp_path: Path):
    run_ws = tmp_path / "run-ws"
    run_ws.mkdir()
    run = engine.create_run(name="agy-run", objective="Run AGY", workspace_path=run_ws)
    task = engine.create_task(run_id=run.run_id, title="Greet", spec="say hello", worker_id="sales")

    dispatch = engine.dispatch_task(
        run_id=run.run_id,
        task_id=task.task_id,
        agent_provider="agy",
        worker_id="sales",
        worktree_path=Path("nested/dir"),
    )

    assert dispatch.worktree_path == str(run_ws / "nested" / "dir")


def test_dry_run_does_not_complete_the_task(engine: OrchestrationEngine, agy_env, tmp_path: Path):
    run = engine.create_run(name="agy-run", objective="Run AGY", workspace_path=tmp_path)
    task = engine.create_task(run_id=run.run_id, title="Greet", spec="say hello", worker_id="sales")

    dispatch = engine.dispatch_task(
        run_id=run.run_id,
        task_id=task.task_id,
        agent_provider="agy",
        worker_id="sales",
        dry_run=True,
    )

    assert dispatch.status == DispatchStatus.SETTLED
    assert dispatch.metadata["dry_run"] is True
    assert dispatch.metadata["plan"]["profile"] == "seekn"
    assert engine.get_task(task.task_id).status == TaskStatus.PENDING


def test_adapter_launch_rejects_channel_session_metadata(agy_env):
    adapter = agy_env["adapter"]
    req = _launch_request(agy_env["workdir"])
    req_blocked = LaunchRequest(
        request_id=req.request_id,
        idempotency_key=req.idempotency_key,
        worker_id=req.worker_id,
        task_id=req.task_id,
        provider=req.provider,
        workspace_path=req.workspace_path,
        prompt=req.prompt,
        metadata={"session_key": "agent:main:main"},
    )
    with pytest.raises(ValueError) as exc:
        adapter.launch(req_blocked)
    assert "Worker execution rejected" in str(exc.value)
    assert "agent:main:main" in str(exc.value)


def test_adapter_launch_records_isolated_session_key(agy_env):
    adapter = agy_env["adapter"]
    handle = adapter.launch(_launch_request(agy_env["workdir"]))
    assert handle.status == ExecutionStatus.COMPLETED
    assert handle.metadata["session_key"] == "agent:sales:worker:conv-abc"
    assert handle.metadata["session_key"] != "agent:main:main"
