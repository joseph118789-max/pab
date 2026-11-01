"""Unit and integration tests for PAB Universal Orchestration Engine and CLI (pab run)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from pab.cli.main import app
from pab.core.config import ConfigManager
from pab.core.exceptions import PABError
from pab.core.models.orchestration import (
    DispatchStatus,
    GateStatus,
    RunStatus,
    TaskStatus,
)
from pab.core.orchestration_engine import OrchestrationEngine


@pytest.fixture
def test_orch_engine(config_mgr: ConfigManager) -> OrchestrationEngine:
    return OrchestrationEngine(config_mgr)


def test_orchestration_run_and_task_lifecycle(test_orch_engine: OrchestrationEngine, tmp_path: Path):
    """Test creating run, adding tasks, and inspecting status."""
    run = test_orch_engine.create_run(
        name="test-feature-run",
        objective="Implement PersonaOS multi-agent review pipeline",
        workspace_path=tmp_path,
        coordinator_agent="claude",
    )
    assert run.run_id.startswith("run-")
    assert run.status == RunStatus.ACTIVE

    task1 = test_orch_engine.create_task(
        run_id=run.run_id,
        title="Architecture spec",
        spec="Design spec for step 11",
        worker_id="personaos-architect",
    )
    assert task1.status == TaskStatus.PENDING
    assert task1.run_id == run.run_id

    task2 = test_orch_engine.create_task(
        run_id=run.run_id,
        title="Implementation",
        spec="Code implementation",
        dependencies=[task1.task_id],
        worker_id="personaos-developer",
    )
    assert task2.dependencies == [task1.task_id]

    tasks = test_orch_engine.list_tasks(run.run_id)
    assert len(tasks) == 2


def test_decision_gate_blocking_and_resolution(test_orch_engine: OrchestrationEngine, tmp_path: Path):
    """Test decision gate blocks task dispatch until resolved."""
    run = test_orch_engine.create_run(name="gated-run", objective="Deploy to production", workspace_path=tmp_path)
    task = test_orch_engine.create_task(run_id=run.run_id, title="Deploy to prod", spec="Run helm upgrade")

    # Create gate blocking the task
    gate = test_orch_engine.create_decision_gate(
        task_id=task.task_id,
        question="Approve production deployment?",
        options=["approve", "reject"],
    )
    assert gate.status == GateStatus.PENDING

    # Verify task is now BLOCKED
    refreshed_task = test_orch_engine.get_task(task.task_id)
    assert refreshed_task.status == TaskStatus.BLOCKED
    assert refreshed_task.gate_id == gate.gate_id

    # Attempting to dispatch blocked task must raise PABError
    with pytest.raises(PABError, match="blocked by pending Decision Gate"):
        test_orch_engine.dispatch_task(
            run_id=run.run_id,
            task_id=task.task_id,
            agent_provider="openclaw",
        )

    # Resolve gate with 'approve'
    resolved_gate = test_orch_engine.resolve_decision_gate(gate.gate_id, choice="approve", resolved_by="lead-architect")
    assert resolved_gate.status == GateStatus.RESOLVED
    assert resolved_gate.resolution == "approve"

    # Verify task is now PENDING and unblocked
    unblocked_task = test_orch_engine.get_task(task.task_id)
    assert unblocked_task.status == TaskStatus.PENDING

    # Now dispatch succeeds
    dispatch = test_orch_engine.dispatch_task(
        run_id=run.run_id,
        task_id=task.task_id,
        agent_provider="openclaw",
        dry_run=True,
    )
    assert dispatch.status == DispatchStatus.SETTLED


def test_use_case_c_multi_reviewer_fan_out(test_orch_engine: OrchestrationEngine, tmp_path: Path):
    """
    Use Case C: One task, multiple independent reviewers (Codex, Claude, Pi).
    Executes parallel dispatches against the same Git commit and aggregates into synthesis report.
    """
    run = test_orch_engine.create_run(
        name="personaos-review",
        objective="Review PersonaOS Step 11 implementation on commit abc123",
        workspace_path=tmp_path,
    )

    t_codex = test_orch_engine.create_task(run.run_id, "Concurrency and DB safety", "Review concurrency and database safety")
    t_claude = test_orch_engine.create_task(run.run_id, "Architecture correctness", "Review architecture and lifecycle correctness")
    t_pi = test_orch_engine.create_task(run.run_id, "Code quality and failovers", "Review code quality and failure scenarios")

    # Dispatch to all three in their respective worktrees
    disp_codex = test_orch_engine.dispatch_task(
        run_id=run.run_id,
        task_id=t_codex.task_id,
        agent_provider="codex",
        worktree_path=tmp_path / "wt-codex",
        dry_run=True,
    )
    disp_claude = test_orch_engine.dispatch_task(
        run_id=run.run_id,
        task_id=t_claude.task_id,
        agent_provider="claude",
        worktree_path=tmp_path / "wt-claude",
        dry_run=True,
    )
    disp_pi = test_orch_engine.dispatch_task(
        run_id=run.run_id,
        task_id=t_pi.task_id,
        agent_provider="pi",
        worktree_path=tmp_path / "wt-pi",
        dry_run=True,
    )

    assert disp_codex.status == DispatchStatus.SETTLED
    assert disp_claude.status == DispatchStatus.SETTLED
    assert disp_pi.status == DispatchStatus.SETTLED

    # Synthesize results
    report = test_orch_engine.get_run_results(run.run_id)
    assert report["total_tasks"] == 3
    assert report["total_dispatches"] == 3

    md = report["report_markdown"]
    assert "CODEX — Concurrency and DB safety" in md
    assert "CLAUDE — Architecture correctness" in md
    assert "PI — Code quality and failovers" in md
    assert "Review PersonaOS Step 11 implementation on commit abc123" in md


def test_cli_pab_run_suite(tmp_path: Path):
    """Test pab run CLI command suite end-to-end using CliRunner."""
    runner = CliRunner()

    # 1. pab run create
    res_create = runner.invoke(app, [
        "run", "create",
        "--name", "cli-test-run",
        "--objective", "Verify CLI orchestration commands",
        "--workspace", str(tmp_path),
        "--json",
    ])
    assert res_create.exit_code == 0
    create_data = json.loads(res_create.output)
    run_id = create_data["run"]["run_id"]
    assert run_id.startswith("run-")

    # 2. pab run list
    res_list = runner.invoke(app, ["run", "list", "--json"])
    assert res_list.exit_code == 0
    list_data = json.loads(res_list.output)
    assert any(r["run_id"] == run_id for r in list_data["runs"])

    # 3. pab run task
    res_task = runner.invoke(app, [
        "run", "task",
        "--run", run_id,
        "--title", "CLI Task 1",
        "--spec", "Verify CLI task creation",
        "--json",
    ])
    assert res_task.exit_code == 0
    task_data = json.loads(res_task.output)
    task_id = task_data["task"]["task_id"]

    # 4. pab run gate create
    res_gate = runner.invoke(app, [
        "run", "gate", "create",
        "--task", task_id,
        "--question", "Ready to dispatch?",
        "--json",
    ])
    assert res_gate.exit_code == 0
    gate_data = json.loads(res_gate.output)
    gate_id = gate_data["gate"]["gate_id"]

    # 5. pab run dispatch should fail while blocked
    res_disp_fail = runner.invoke(app, [
        "run", "dispatch",
        "--run", run_id,
        "--task", task_id,
        "--agent", "codex",
    ])
    assert res_disp_fail.exit_code == 1
    assert "blocked by pending" in res_disp_fail.output and "Decision Gate" in res_disp_fail.output

    # 6. pab run gate resolve
    res_resolve = runner.invoke(app, [
        "run", "gate", "resolve",
        "--gate", gate_id,
        "--choice", "approve",
        "--json",
    ])
    assert res_resolve.exit_code == 0

    # 7. pab run dispatch now succeeds
    res_disp = runner.invoke(app, [
        "run", "dispatch",
        "--run", run_id,
        "--task", task_id,
        "--agent", "pi",
        "--dry-run",
        "--json",
    ])
    assert res_disp.exit_code == 0
    disp_data = json.loads(res_disp.output)
    assert disp_data["dispatch"]["agent_provider"] == "pi"

    # 8. pab run results
    res_results = runner.invoke(app, ["run", "results", "--run", run_id])
    assert res_results.exit_code == 0
    assert "PAB Multi-Agent Orchestration Synthesis Report" in res_results.output
    assert "PI — CLI Task 1" in res_results.output
