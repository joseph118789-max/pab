"""Real AGY integration tests for the five Sentinel Ops workers.

These tests spawn the real ``agy`` CLI against the real isolated AGY profiles
(``~/.agy-<profile>``). They are skipped unless ``PAB_AGY_INTEGRATION=1`` is set.

Run with::

    PAB_AGY_INTEGRATION=1 python3 -m pytest tests/test_agy_integration.py -v
"""

import os
from pathlib import Path

import pytest

from pab.core.config import ConfigManager
from pab.core.models.execution import ExecutionStatus
from pab.core.models.orchestration import DispatchStatus, TaskStatus
from pab.core.orchestration_engine import OrchestrationEngine
from pab.providers.agy.execution import AgyRunner
from pab.providers.agy.workers import AgyWorkerRegistry

WORKER_IDS = ["automation", "delivery", "qa", "research", "sales"]

READ_ONLY_PROMPT = (
    "Reply with exactly one line in the form: PAB_AGY_OK {worker_id}. Do not use any tools."
)


def _integration_enabled() -> bool:
    return os.environ.get("PAB_AGY_INTEGRATION") == "1"


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def registry() -> AgyWorkerRegistry:
    return AgyWorkerRegistry.from_config()


@pytest.fixture
def skip_without_integration():
    if not _integration_enabled():
        pytest.skip("Set PAB_AGY_INTEGRATION=1 to run real AGY integration tests.")


@pytest.mark.parametrize("worker_id", WORKER_IDS)
def test_agy_worker_real_execution(worker_id, registry, skip_without_integration):
    """A real, read-only AGY turn runs under the worker's isolated profile."""
    worker = registry.resolve(worker_id=worker_id)
    runner = AgyRunner(default_timeout=600)

    result = runner.run(worker, prompt=READ_ONLY_PROMPT.format(worker_id=worker_id), timeout=600)

    assert result.ok is True, f"AGY execution failed: {result.error} / {result.stderr_tail[-500:]}"
    assert result.exit_code == 0
    assert result.status == "SUCCESS"
    assert result.conversation_id, "AGY must return a conversation id (trace id)"
    assert "PAB_AGY_OK" in result.response

    # Correct profile was used.
    assert result.profile == worker.profile
    assert result.profile_home == str(worker.profile_home)

    # Correct working directory was used.
    assert result.workdir == str(worker.workdir)

    # Trace artefacts exist for the conversation, under the worker's profile home.
    assert result.trace_path and Path(result.trace_path).is_file()
    assert result.trace_path.startswith(str(worker.profile_home))
    assert result.conversation_id in result.trace_path

    # Profile isolation proof: the AGY CLI log artifact was written under the
    # worker's own profile home during this execution.
    assert result.profile_log and Path(result.profile_log).is_file()
    assert str(result.profile_log).startswith(str(worker.profile_home))


@pytest.mark.parametrize("worker_id", WORKER_IDS)
def test_pab_dispatch_real_execution(worker_id, tmp_path, skip_without_integration):
    """The full PAB stack (OpenClaw → PAB → AGY) dispatches and records reality."""
    engine = OrchestrationEngine(ConfigManager(root_dir=tmp_path / ".pab"))

    run = engine.create_run(
        name=f"agy-integration-{worker_id}",
        objective=f"Verify real AGY execution for {worker_id}",
        workspace_path=tmp_path,
    )
    task = engine.create_task(
        run_id=run.run_id,
        title=f"{worker_id} read-only verification",
        spec=READ_ONLY_PROMPT.format(worker_id=worker_id),
        worker_id=worker_id,
    )

    dispatch = engine.dispatch_task(
        run_id=run.run_id,
        task_id=task.task_id,
        agent_provider="agy",
        worker_id=worker_id,
        timeout_seconds=600,
    )

    # Dispatch + task status reflect the real execution.
    assert dispatch.status == DispatchStatus.SETTLED
    assert engine.get_task(task.task_id).status == TaskStatus.COMPLETED

    # Dispatch record carries the real trace id and profile.
    assert dispatch.metadata["conversation_id"]
    assert dispatch.metadata["profile"]
    assert dispatch.metadata["response"]
    assert "PAB_AGY_OK" in dispatch.metadata["response"]
    assert dispatch.metadata["workdir"] == dispatch.worktree_path

    # PAB execution record matches the actual execution.
    executions = engine.db.list_executions(provider="agy")
    assert len(executions) == 1
    execution = executions[0]
    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.exit_code == 0
    assert execution.native_session_id == dispatch.metadata["conversation_id"]
    assert execution.metadata["conversation_id"] == dispatch.metadata["conversation_id"]
    assert execution.workspace == dispatch.worktree_path

    # The stored dispatch mirrors the stored execution.
    stored = engine.db.get_dispatch(dispatch.dispatch_id)
    assert stored.status == DispatchStatus.SETTLED
    assert stored.metadata["conversation_id"] == execution.native_session_id
