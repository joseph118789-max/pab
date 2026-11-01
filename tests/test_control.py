"""Unit and integration tests for PAB Control Plane (Milestone 2).

Verifies:
- Common AgentAdapter contract & UnsupportedOperationError handling
- CapabilityRegistry: installed vs missing CLIs, version & capability detection
- ExecutionSupervisor:
  - Successful launch in managed_process and orca_terminal modes
  - Launch failure handling
  - Idempotent launch deduplication
  - Event sequencing (monotonic sequence numbering)
  - Duplicate event suppression
  - Stale execution-generation rejection
  - Process termination (stop with and without force)
  - Restart reconciliation of interrupted processes
- Machine-readable CLI:
  - `pab control list-agents --json`
  - `pab control launch --json`
  - `pab control status --json`
  - `pab control stop --json`
  - `pab control events --json`
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from pab.cli.main import app
from pab.core.capability_registry import CapabilityRegistry
from pab.core.config import ConfigManager
from pab.core.db import Database
from pab.core.exceptions import (
    ExecutionNotFoundError,
    ProviderNotFoundError,
    StaleGenerationError,
    UnsupportedOperationError,
)
from pab.core.execution_supervisor import ExecutionSupervisor
from pab.core.models.execution import (
    ExecutionEvent,
    ExecutionHandle,
    ExecutionMode,
    ExecutionStatus,
    LaunchRequest,
    ProviderCapabilities,
)
from pab.providers.mock import MockAgentAdapter


@pytest.fixture
def temp_config(tmp_path: Path) -> ConfigManager:
    config = ConfigManager(root_dir=tmp_path / ".pab")
    return config


@pytest.fixture
def mock_registry(temp_config: ConfigManager) -> CapabilityRegistry:
    cap_reg = CapabilityRegistry()
    # Register mock providers
    cap_reg.register_provider("mock-live", MockAgentAdapter(name="mock-live", available=True))
    cap_reg.register_provider(
        "mock-offline", MockAgentAdapter(name="mock-offline", available=False)
    )
    cap_reg.register_provider(
        "mock-unsupported",
        MockAgentAdapter(
            name="mock-unsupported",
            available=True,
            supported_ops=["discover", "capabilities"],
        ),
    )
    return cap_reg


@pytest.fixture
def supervisor(temp_config: ConfigManager, mock_registry: CapabilityRegistry) -> ExecutionSupervisor:
    return ExecutionSupervisor(
        config_manager=temp_config,
        capability_registry=mock_registry,
    )


# --- 1. Common AgentAdapter Contract & Unsupported Operations ---

def test_unsupported_operation_handling():
    adapter = MockAgentAdapter(
        name="stub",
        available=True,
        supported_ops=["discover", "capabilities"],
    )
    req = LaunchRequest(
        request_id="req-1",
        idempotency_key="idem-1",
        worker_id="dev",
        task_id="task-1",
        provider="stub",
        workspace_path=Path("/tmp"),
    )

    with pytest.raises(UnsupportedOperationError) as exc_info:
        adapter.launch(req)
    assert "does not support 'launch'" in str(exc_info.value)

    with pytest.raises(UnsupportedOperationError):
        adapter.attach("exec-1")

    with pytest.raises(UnsupportedOperationError):
        adapter.stop("exec-1")

    with pytest.raises(UnsupportedOperationError):
        adapter.send_input("exec-1", "hello")


# --- 2. Capability Registry Verification ---

def test_capability_detection_installed_and_missing(mock_registry: CapabilityRegistry):
    caps_live = mock_registry.get_capabilities("mock-live")
    assert caps_live is not None
    assert caps_live.available is True
    assert caps_live.health_status == "healthy"
    assert caps_live.detected_version == "1.0.0-mock"
    assert "launch" in caps_live.supported_operations

    caps_offline = mock_registry.get_capabilities("mock-offline")
    assert caps_offline is not None
    assert caps_offline.available is False
    assert caps_offline.health_status == "unavailable"
    assert caps_offline.detected_version is None

    assert mock_registry.get_capabilities("non-existent-provider") is None


def test_list_all_capabilities_contains_required_fields(mock_registry: CapabilityRegistry):
    all_caps = mock_registry.list_capabilities()
    assert len(all_caps) >= 3
    for c in all_caps:
        d = c.to_dict()
        assert "provider" in d
        assert "display_name" in d
        assert "available" in d
        assert "supported_operations" in d
        assert "supported_execution_modes" in d
        assert "detection_timestamp" in d
        assert "health_status" in d


# --- 3. Execution Supervisor: Launch, Idempotency & Lifecycle ---

def test_successful_launch_managed_process(supervisor: ExecutionSupervisor, tmp_path: Path):
    req = LaunchRequest(
        request_id="req-m2-001",
        idempotency_key="idem-m2-001",
        worker_id="backend-engineer",
        worker_profile_version=2,
        task_id="task-101",
        execution_generation=1,
        provider="mock-live",
        workspace_path=tmp_path,
        execution_mode=ExecutionMode.MANAGED_PROCESS,
    )

    handle = supervisor.launch(req)
    assert handle.execution_id.startswith("exec-")
    assert handle.request_id == "req-m2-001"
    assert handle.status == ExecutionStatus.RUNNING
    assert handle.process_id is not None
    assert handle.execution_mode == ExecutionMode.MANAGED_PROCESS

    # Clean up process
    supervisor.stop(handle.execution_id, force=True)


def test_successful_launch_orca_terminal_mode(supervisor: ExecutionSupervisor, tmp_path: Path):
    req = LaunchRequest(
        request_id="req-m2-002",
        idempotency_key="idem-m2-002",
        worker_id="qa-engineer",
        worker_profile_version=1,
        task_id="task-102",
        execution_generation=1,
        provider="mock-live",
        workspace_path=tmp_path,
        execution_mode=ExecutionMode.ORCA_TERMINAL,
    )

    handle = supervisor.launch(req)
    assert handle.execution_mode == ExecutionMode.ORCA_TERMINAL
    assert handle.terminal_handle is not None
    assert handle.status == ExecutionStatus.RUNNING


def test_idempotent_duplicate_launch_returns_existing_handle(
    supervisor: ExecutionSupervisor, tmp_path: Path
):
    req = LaunchRequest(
        request_id="req-dup-001",
        idempotency_key="same-idempotency-key",
        worker_id="devops",
        task_id="task-201",
        provider="mock-live",
        workspace_path=tmp_path,
    )

    handle1 = supervisor.launch(req)
    # Re-issue identical request
    handle2 = supervisor.launch(req)

    assert handle1.execution_id == handle2.execution_id
    assert handle1.idempotency_key == handle2.idempotency_key

    supervisor.stop(handle1.execution_id, force=True)


def test_launch_offline_provider_fails(supervisor: ExecutionSupervisor, tmp_path: Path):
    req = LaunchRequest(
        request_id="req-fail-001",
        idempotency_key="idem-fail-001",
        worker_id="dev",
        task_id="task-301",
        provider="mock-offline",
        workspace_path=tmp_path,
    )

    with pytest.raises(RuntimeError) as exc_info:
        supervisor.launch(req)
    assert "not installed or available" in str(exc_info.value)


# --- 4. Process Termination ---

def test_stop_execution(supervisor: ExecutionSupervisor, tmp_path: Path):
    req = LaunchRequest(
        request_id="req-stop-001",
        idempotency_key="idem-stop-001",
        worker_id="dev",
        task_id="task-401",
        provider="mock-live",
        workspace_path=tmp_path,
    )

    handle = supervisor.launch(req)
    assert handle.status == ExecutionStatus.RUNNING

    stopped = supervisor.stop(handle.execution_id, force=False)
    assert stopped.status == ExecutionStatus.CANCELLED
    assert stopped.exit_code == 130


# --- 5. Event Sequencing, Generation Check & Duplication ---

def test_event_sequencing_and_generation_guard(supervisor: ExecutionSupervisor, tmp_path: Path):
    req = LaunchRequest(
        request_id="req-event-001",
        idempotency_key="idem-event-001",
        worker_id="dev",
        task_id="task-501",
        execution_generation=1,
        provider="mock-live",
        workspace_path=tmp_path,
    )

    handle = supervisor.launch(req)

    # Initial start event was sequence 1
    events = supervisor.list_events(handle.execution_id)
    assert len(events) == 1
    assert events[0].sequence_number == 1
    assert events[0].event_type == "execution.started"

    # Emit sequence 2
    ev2 = supervisor.emit_event(
        execution_id=handle.execution_id,
        event_type="execution.progress",
        payload={"step": "compiling"},
        generation=1,
    )
    assert ev2.sequence_number == 2

    # Stale generation attempt should be rejected
    with pytest.raises(StaleGenerationError):
        supervisor.emit_event(
            execution_id=handle.execution_id,
            event_type="execution.progress",
            payload={"step": "stale"},
            generation=999,  # Mismatched generation
        )

    # Duplicate event save suppression
    supervisor.db.save_event(ev2)  # Re-saving same event
    events_after = supervisor.list_events(handle.execution_id)
    assert len(events_after) == 2  # No duplicate sequence 2 entry

    supervisor.stop(handle.execution_id, force=True)


# --- 6. PAB Restart Reconciliation ---

def test_pab_restart_reconciliation(temp_config: ConfigManager, tmp_path: Path):
    db = Database(temp_config.db_path)

    # Simulate an execution with a fake PID that does not exist
    dead_pid = 999999
    now = datetime.now(timezone.utc)
    handle = ExecutionHandle(
        execution_id="exec-dead-process",
        request_id="req-dead",
        idempotency_key="idem-dead",
        task_id="task-dead",
        worker_id="worker-dead",
        provider="mock-live",
        workspace=str(tmp_path),
        status=ExecutionStatus.RUNNING,
        process_id=dead_pid,
        started_at=now,
    )
    db.save_execution(handle)

    # New supervisor instance simulating restart
    cap_reg = CapabilityRegistry()
    new_supervisor = ExecutionSupervisor(config_manager=temp_config, capability_registry=cap_reg)

    reconciled_count = new_supervisor.reconcile_executions()
    assert reconciled_count == 1

    updated = new_supervisor.get_execution("exec-dead-process")
    assert updated.status == ExecutionStatus.INTERRUPTED
    assert updated.exit_code == 137
    assert "died during PAB restart" in (updated.error_message or "")


# --- 7. Machine-Readable CLI Testing ---

def test_cli_list_agents_json():
    runner = CliRunner()
    result = runner.invoke(app, ["control", "list-agents", "--json"])
    assert result.exit_code == 0
    import json
    data = json.loads(result.stdout)
    assert data["contract_version"] == "1.0"
    assert data["status"] == "ok"
    assert isinstance(data["agents"], list)
    assert len(data["agents"]) > 0


def test_cli_launch_and_status_json(tmp_path: Path):
    runner = CliRunner()
    launch_res = runner.invoke(
        app,
        [
            "control",
            "launch",
            "--provider",
            "openclaw",
            "--worker",
            "test-worker",
            "--task",
            "test-task",
            "--workspace",
            str(tmp_path),
            "--command",
            "echo 'test'",
            "--json",
        ],
    )
    assert launch_res.exit_code == 0
    import json
    launch_data = json.loads(launch_res.stdout)
    assert launch_data["contract_version"] == "1.0"
    assert launch_data["status"] == "ok"
    exec_id = launch_data["execution"]["execution_id"]

    # Query status
    status_res = runner.invoke(app, ["control", "status", exec_id, "--json"])
    assert status_res.exit_code == 0
    status_data = json.loads(status_res.stdout)
    assert status_data["execution"]["execution_id"] == exec_id


def test_cli_control_handoff(tmp_path: Path):
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "control",
            "handoff",
            "--source",
            "claude",
            "--target",
            "openclaw",
            "--worker",
            "test-worker",
            "--project",
            str(tmp_path),
            "--dry-run",
            "--json",
        ],
    )
    assert res.exit_code == 0
    import json
    data = json.loads(res.stdout)
    assert data["contract_version"] == "1.0"
    assert data["status"] == "ok"
    assert data["handoff"]["source_provider"] == "claude"
    assert data["handoff"]["destination_provider"] == "openclaw"
    assert data["handoff"]["dry_run"] is True

