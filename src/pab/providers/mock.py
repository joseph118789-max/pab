"""Deterministic Mock Agent Adapter for testing and verification."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from pab.core.exceptions import UnsupportedOperationError
from pab.core.models.agent import CanonicalAgentDefinition
from pab.core.models.execution import (
    ExecutionEvent,
    ExecutionHandle,
    ExecutionMode,
    ExecutionStatus,
    LaunchRequest,
    ProviderCapabilities,
)
from pab.core.models.session import NormalizedSession
from pab.core.models.skill import CanonicalSkill
from pab.providers.base import AgentAdapter


class MockAgentAdapter(AgentAdapter):
    """Mock agent adapter simulating external CLI process lifecycles."""

    def __init__(
        self,
        name: str = "mock",
        display_name: str = "Mock Test Agent",
        version_str: str = "1.0.0-mock",
        available: bool = True,
        supported_ops: Optional[List[str]] = None,
        should_fail_launch: bool = False,
        simulate_crash: bool = False,
    ):
        self._name = name
        self._display_name = display_name
        self._version = version_str
        self._available = available
        self._should_fail_launch = should_fail_launch
        self._simulate_crash = simulate_crash
        self._supported_ops = supported_ops or [
            "discover",
            "capabilities",
            "launch",
            "attach",
            "resume",
            "inspect",
            "stop",
            "stream_events",
            "send_input",
            "export_session",
            "import_context",
        ]
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self.execution_records: Dict[str, ExecutionHandle] = {}
        self.events: Dict[str, List[ExecutionEvent]] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._display_name

    def detect(self) -> bool:
        return self._available

    def version(self) -> Optional[str]:
        return self._version if self._available else None

    def capabilities(self) -> Dict[str, Any]:
        return {
            "agent_management": True,
            "skills": True,
            "sessions": True,
            "native_resume": True,
            "skill_formats": ["open-agent-skills", "mock-format"],
            "required_configuration": {},
        }

    def supported_operations(self) -> List[str]:
        return list(self._supported_ops)

    def supported_execution_modes(self) -> List[str]:
        return [ExecutionMode.MANAGED_PROCESS.value, ExecutionMode.ORCA_TERMINAL.value]

    def get_executable_path(self) -> Optional[str]:
        return "/usr/bin/mock-agent" if self._available else None

    def launch(self, request: LaunchRequest) -> ExecutionHandle:
        if "launch" not in self._supported_ops:
            raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'launch'")

        if self._should_fail_launch:
            raise RuntimeError(f"Simulated launch failure for worker '{request.worker_id}'")

        exec_id = f"exec-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # In managed_process mode, spawn a lightweight sleeper process
        pid = None
        term_handle = None

        if request.execution_mode == ExecutionMode.MANAGED_PROCESS:
            # Spawn a harmless sleep/python process
            cmd = request.command or [sys.executable, "-c", "import time; time.sleep(30)"]
            if isinstance(cmd, str):
                cmd = [sys.executable, "-c", f"import time; time.sleep(30)"]
            proc = subprocess.Popen(
                cmd,
                cwd=str(request.workspace_path) if request.workspace_path.is_dir() else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            pid = proc.pid
            self.active_processes[exec_id] = proc
        elif request.execution_mode == ExecutionMode.ORCA_TERMINAL:
            term_handle = f"term_mock_{uuid.uuid4().hex[:8]}"

        status = ExecutionStatus.RUNNING
        handle = ExecutionHandle(
            execution_id=exec_id,
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            task_id=request.task_id,
            worker_id=request.worker_id,
            worker_profile_version=request.worker_profile_version,
            execution_generation=request.execution_generation,
            provider=self.name,
            execution_mode=request.execution_mode,
            workspace=str(request.workspace_path),
            status=status,
            native_session_id=f"sess-mock-{uuid.uuid4().hex[:6]}",
            process_id=pid,
            terminal_handle=term_handle,
            exit_code=None,
            started_at=now,
            last_event_sequence=1,
            metadata={"mock": True, **request.metadata},
        )
        self.execution_records[exec_id] = handle

        # Record initial started event
        start_event = ExecutionEvent(
            event_id=f"evt-{uuid.uuid4().hex[:10]}",
            execution_id=exec_id,
            request_id=request.request_id,
            execution_generation=request.execution_generation,
            sequence_number=1,
            event_type="execution.started",
            timestamp=now,
            payload={"provider": self.name, "pid": pid, "terminal_handle": term_handle},
        )
        self.events[exec_id] = [start_event]

        return handle

    def inspect(self, execution_id: str) -> ExecutionHandle:
        if "inspect" not in self._supported_ops:
            raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'inspect'")

        handle = self.execution_records.get(execution_id)
        if not handle:
            raise KeyError(f"Execution {execution_id} not found in mock adapter")

        # Check if process is still running
        proc = self.active_processes.get(execution_id)
        if proc:
            poll = proc.poll()
            if poll is not None:
                # Process finished
                handle = ExecutionHandle(
                    execution_id=handle.execution_id,
                    request_id=handle.request_id,
                    idempotency_key=handle.idempotency_key,
                    task_id=handle.task_id,
                    worker_id=handle.worker_id,
                    worker_profile_version=handle.worker_profile_version,
                    execution_generation=handle.execution_generation,
                    provider=handle.provider,
                    execution_mode=handle.execution_mode,
                    workspace=handle.workspace,
                    status=ExecutionStatus.COMPLETED if poll == 0 else ExecutionStatus.FAILED,
                    native_session_id=handle.native_session_id,
                    process_id=handle.process_id,
                    terminal_handle=handle.terminal_handle,
                    exit_code=poll,
                    started_at=handle.started_at,
                    completed_at=datetime.now(timezone.utc),
                    last_event_sequence=handle.last_event_sequence,
                    error_message=None if poll == 0 else f"Process exited with code {poll}",
                    metadata=handle.metadata,
                )
                self.execution_records[execution_id] = handle

        return handle

    def stop(self, execution_id: str, force: bool = False) -> bool:
        if "stop" not in self._supported_ops:
            raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'stop'")

        proc = self.active_processes.get(execution_id)
        if proc:
            try:
                if force:
                    proc.kill()
                else:
                    proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()

        handle = self.execution_records.get(execution_id)
        if handle:
            self.execution_records[execution_id] = ExecutionHandle(
                execution_id=handle.execution_id,
                request_id=handle.request_id,
                idempotency_key=handle.idempotency_key,
                task_id=handle.task_id,
                worker_id=handle.worker_id,
                worker_profile_version=handle.worker_profile_version,
                execution_generation=handle.execution_generation,
                provider=handle.provider,
                execution_mode=handle.execution_mode,
                workspace=handle.workspace,
                status=ExecutionStatus.CANCELLED,
                native_session_id=handle.native_session_id,
                process_id=handle.process_id,
                terminal_handle=handle.terminal_handle,
                exit_code=130 if not force else 137,
                started_at=handle.started_at,
                completed_at=datetime.now(timezone.utc),
                last_event_sequence=handle.last_event_sequence + 1,
                error_message="Process terminated by operator stop request",
                metadata=handle.metadata,
            )
        return True

    def stream_events(self, execution_id: str) -> Iterator[ExecutionEvent]:
        if "stream_events" not in self._supported_ops:
            raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'stream_events'")
        for ev in self.events.get(execution_id, []):
            yield ev

    def send_input(self, execution_id: str, message: str) -> bool:
        if "send_input" not in self._supported_ops:
            raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'send_input'")
        return True

    # Required AgentProvider abstract methods for compatibility
    def list_agents(self) -> List[Dict[str, Any]]:
        return []

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return None

    def create_agent(self, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return {"id": definition.id, "status": "created"}

    def update_agent(self, agent_id: str, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return {"id": agent_id, "status": "updated"}

    def delete_agent(self, agent_id: str) -> bool:
        return True

    def list_skills(self) -> List[Dict[str, Any]]:
        return []

    def install_skill(self, skill: CanonicalSkill) -> bool:
        return True

    def remove_skill(self, skill_id: str) -> bool:
        return True

    def list_sessions(self) -> List[Dict[str, Any]]:
        return []

    def export_session(self, session_id: str) -> Optional[NormalizedSession]:
        return None

    def resume_session(self, session_id: str) -> bool:
        return True

    def validate(self, definition: CanonicalAgentDefinition) -> List[str]:
        return []

    def export_canonical_agent(self, agent_id: str) -> Optional[CanonicalAgentDefinition]:
        return None
