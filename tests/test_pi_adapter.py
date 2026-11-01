"""Unit and integration tests for Pi Coding Agent adapter and RPC protocol."""

import json
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pab.core.models.execution import (
    ExecutionMode,
    ExecutionStatus,
    LaunchRequest,
)
from pab.providers.pi.adapter import PiAdapter
from pab.providers.pi.config import get_pi_bin, get_pi_home
from pab.providers.pi.rpc import PiRpcClient, PiRpcError


def test_pi_discovery_and_version():
    """AT-1: Detect Pi installation and version."""
    adapter = PiAdapter()
    assert adapter.name == "pi"
    assert adapter.display_name == "Pi Coding Agent"
    bin_path = adapter.get_executable_path()
    assert bin_path is not None
    assert adapter.detect() is True

    ver = adapter.version()
    assert ver is not None
    assert "1." in ver  # Expected 1.4.0 on current system


def test_pi_capabilities():
    """Verify Pi adapter capabilities declaration."""
    adapter = PiAdapter()
    caps = adapter.capabilities()
    assert caps["rpc_mode"] is True
    assert caps["native_resume"] is True
    assert caps["skills"] is True
    assert caps["sessions"] is True
    assert caps["interactive_tui"] is True
    assert "AGENTS.md" in caps["instruction_files"]


def test_pi_rpc_client_protocol_mock(tmp_path: Path):
    """AT-3 & AT-4: Test PiRpcClient command correlation and event streaming over mock pipe."""
    # Create a mock subprocess script that behaves like Pi RPC
    mock_script = tmp_path / "mock_pi.py"
    mock_script.write_text(
        """import sys, json

# Initial UI request
sys.stdout.write(json.dumps({"type": "extension_ui_request", "id": "ui-1", "method": "setTitle", "title": "π - mock"}) + "\\n")
sys.stdout.flush()

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    cmd = json.loads(line)
    req_id = cmd.get("id", "none")
    cmd_type = cmd.get("type")

    if cmd_type == "prompt":
        sys.stdout.write(json.dumps({"id": req_id, "type": "response", "command": "prompt", "success": True, "data": {"disposition": "started"}}) + "\\n")
        sys.stdout.write(json.dumps({"type": "agent_start"}) + "\\n")
        sys.stdout.write(json.dumps({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Mock code review: all tests pass."}}) + "\\n")
        sys.stdout.write(json.dumps({"type": "tool_execution", "tool": "read", "path": "test.py"}) + "\\n")
        sys.stdout.write(json.dumps({"type": "agent_end"}) + "\\n")
        sys.stdout.write(json.dumps({"type": "agent_settled"}) + "\\n")
        sys.stdout.flush()

    elif cmd_type == "get_state":
        sys.stdout.write(json.dumps({"id": req_id, "type": "response", "command": "get_state", "success": True, "data": {"model": "mock-model"}}) + "\\n")
        sys.stdout.flush()

    elif cmd_type == "abort":
        sys.stdout.write(json.dumps({"id": req_id, "type": "response", "command": "abort", "success": True}) + "\\n")
        sys.stdout.flush()
""",
        encoding="utf-8",
    )

    client = PiRpcClient(
        executable_path=str(mock_script),
        workspace_path=tmp_path,
    )
    client.start()
    assert client.is_alive is True

    # Test event capturing
    events_received = []
    client.add_event_listener(lambda ev: events_received.append(ev.get("type")))

    # Test get_state command
    state = client.get_state()
    assert state.get("model") == "mock-model"

    # Test prompt and wait for agent_settled
    res = client.prompt("Review code", timeout=5.0)
    assert res.get("disposition") == "started"
    assert "Mock code review" in res.get("text")

    # Verify event sequencing: agent_start -> message_update -> tool_execution -> agent_end -> agent_settled
    assert "agent_start" in events_received
    assert "message_update" in events_received
    assert "tool_execution" in events_received
    assert "agent_end" in events_received
    assert "agent_settled" in events_received

    client.close()
    assert client.is_alive is False


def test_pi_adapter_launch_and_inspect(tmp_path: Path):
    """AT-2 & AT-5: Test PiAdapter launch, inspect, prompt, and stop lifecycle."""
    adapter = PiAdapter(workspace_root=tmp_path)

    # Use a dummy script as executable for testing adapter
    dummy_exe = tmp_path / "dummy_pi.py"
    dummy_exe.write_text(
        """import sys, json, time
for line in sys.stdin:
    cmd = json.loads(line)
    req_id = cmd.get("id")
    sys.stdout.write(json.dumps({"id": req_id, "type": "response", "command": cmd.get("type"), "success": True, "data": {"disposition": "handled"}}) + "\\n")
    sys.stdout.flush()
""",
        encoding="utf-8",
    )

    with patch.object(adapter, "get_executable_path", return_value="python3"):
        req = LaunchRequest(
            request_id="req-test-1",
            idempotency_key="idem-test-1",
            worker_id="personaos-qa",
            task_id="task-101",
            provider="pi",
            workspace_path=tmp_path,
            execution_mode=ExecutionMode.MANAGED_PROCESS,
        )

        with patch("pab.providers.pi.adapter.PiRpcClient") as MockClientClass:
            mock_client = MagicMock()
            mock_client.pid = 9999
            mock_client.is_alive = True
            mock_client.is_running = False
            mock_client.prompt.return_value = {"text": "Review complete"}
            MockClientClass.return_value = mock_client

            handle = adapter.launch(req)
            assert handle.status == ExecutionStatus.RUNNING
            assert handle.process_id == 9999
            assert handle.worker_id == "personaos-qa"

            # Test prompt
            prompt_res = adapter.prompt(handle.execution_id, "Check tests")
            assert prompt_res["text"] == "Review complete"

            # Test inspect
            inspected = adapter.inspect(handle.execution_id)
            assert inspected.execution_id == handle.execution_id

            # Test stop
            stopped = adapter.stop(handle.execution_id)
            assert stopped is True
            mock_client.close.assert_called_once()


def test_pi_resume_session_check(tmp_path: Path):
    """Test resume_session checks existing session files."""
    adapter = PiAdapter(home_dir=tmp_path)
    sessions_dir = tmp_path / "sessions" / "test-project"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    sess_file = sessions_dir / "sess-abc123.jsonl"
    sess_file.write_text('{"type":"session","id":"abc123"}\n', encoding="utf-8")

    with patch("pab.providers.pi.adapter.get_pi_sessions_dir", return_value=tmp_path / "sessions"):
        assert adapter.resume_session("pi:sess-abc123") is True
        assert adapter.resume_session("pi:non-existent") is False
