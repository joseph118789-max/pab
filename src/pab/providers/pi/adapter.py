"""Pi Coding Agent Provider Adapter."""

import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from pab.core.exceptions import ExecutionNotFoundError, UnsupportedOperationError
from pab.core.models.agent import CanonicalAgentDefinition
from pab.core.models.execution import (
    ExecutionEvent,
    ExecutionHandle,
    ExecutionMode,
    ExecutionStatus,
    LaunchRequest,
)
from pab.core.models.session import NormalizedSession
from pab.core.models.skill import CanonicalSkill
from pab.providers.base import AgentAdapter
from pab.providers.pi.agents import (
    compile_pi_agent,
    delete_pi_agent,
    list_pi_agents,
)
from pab.providers.pi.config import (
    get_pi_bin,
    get_pi_home,
    get_pi_sessions_dir,
)
from pab.providers.pi.memory import list_pi_memories
from pab.providers.pi.rpc import PiRpcClient, PiRpcError
from pab.providers.pi.sessions import (
    export_pi_session,
    list_pi_sessions,
)
from pab.providers.pi.skills import (
    install_pi_skill,
    list_pi_skills,
    remove_pi_skill,
)


class PiAdapter(AgentAdapter):
    """Universal runtime adapter for Pi Coding Agent platform."""

    def __init__(
        self,
        home_dir: Optional[Path] = None,
        workspace_root: Optional[Path] = None,
    ):
        self._home = home_dir or get_pi_home()
        self._workspace_root = workspace_root
        self._active_clients: Dict[str, PiRpcClient] = {}
        self._active_handles: Dict[str, ExecutionHandle] = {}
        self._event_queues: Dict[str, List[ExecutionEvent]] = {}
        self._lock = threading.Lock()

    def get_executable_path(self) -> Optional[str]:
        return get_pi_bin() or "/usr/bin/pi"

    def supported_operations(self) -> List[str]:
        return [
            "discover",
            "capabilities",
            "list_agents",
            "get_agent",
            "create_agent",
            "update_agent",
            "delete_agent",
            "list_skills",
            "install_skill",
            "remove_skill",
            "list_sessions",
            "export_session",
            "resume",
            "launch",
            "stop",
            "inspect",
            "stream_events",
            "send_input",
            "prompt",
        ]

    def supported_execution_modes(self) -> List[str]:
        return [
            ExecutionMode.MANAGED_PROCESS.value,
            ExecutionMode.ORCA_TERMINAL.value,
        ]

    @property
    def name(self) -> str:
        return "pi"

    @property
    def display_name(self) -> str:
        return "Pi Coding Agent"

    def detect(self) -> bool:
        return bool(get_pi_bin() or self._home.is_dir())

    def version(self) -> Optional[str]:
        bin_path = get_pi_bin()
        if bin_path:
            try:
                proc = subprocess.run(
                    [bin_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if proc.returncode == 0:
                    return proc.stdout.strip()
            except Exception:
                pass
        return None

    def capabilities(self) -> Dict[str, Any]:
        return {
            "provider": "pi",
            "display_name": "Pi Coding Agent",
            "agent_management": True,
            "markdown_agents": True,
            "skills": True,
            "extensions": True,
            "memory": True,
            "sessions": True,
            "native_resume": True,
            "rpc_mode": True,
            "json_mode": True,
            "print_mode": True,
            "interactive_tui": True,
            "instruction_files": ["AGENTS.md", "CLAUDE.md"],
            "skill_formats": ["open-agent-skills"],
            "supported_models": ["anthropic/*", "openai/*", "gemini/*", "deepseek/*"],
        }

    def launch(self, request: LaunchRequest) -> ExecutionHandle:
        """Launch a Pi session under supervised RPC mode or interactive mode."""
        exec_id = f"exec-pi-{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)
        bin_path = self.get_executable_path()
        if not bin_path:
            raise RuntimeError("Pi executable not found on system PATH or standard locations.")

        native_sess_id = f"pi-{uuid.uuid4().hex[:8]}"

        # Parse append system prompt if provided
        append_prompt = None
        if request.system_prompt:
            append_prompt = request.system_prompt

        client = PiRpcClient(
            executable_path=bin_path,
            workspace_path=request.workspace_path,
            session_id=native_sess_id,
            model=request.model,
            append_system_prompt=append_prompt,
            env=request.environment,
        )

        try:
            client.start()
        except Exception as exc:
            return ExecutionHandle(
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
                status=ExecutionStatus.FAILED,
                started_at=now,
                error_message=str(exc),
                exit_code=1,
            )

        with self._lock:
            self._active_clients[exec_id] = client
            self._event_queues[exec_id] = []

        # Register event translator
        seq_counter = [1]

        def _on_event(raw_event: Dict[str, Any]):
            ev_type = raw_event.get("type", "unknown")
            seq = seq_counter[0]
            seq_counter[0] += 1
            canonical_type = "execution.event"
            if ev_type == "agent_start":
                canonical_type = "execution.turn_started"
            elif ev_type == "message_update":
                canonical_type = "execution.message"
            elif ev_type == "tool_execution":
                canonical_type = "execution.tool_call"
            elif ev_type == "agent_end":
                canonical_type = "execution.turn_completed"
            elif ev_type == "agent_settled":
                canonical_type = "execution.settled"

            ev = ExecutionEvent(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                execution_id=exec_id,
                request_id=request.request_id,
                execution_generation=request.execution_generation,
                sequence_number=seq,
                event_type=canonical_type,
                timestamp=datetime.now(timezone.utc),
                payload=raw_event,
            )
            with self._lock:
                if exec_id in self._event_queues:
                    self._event_queues[exec_id].append(ev)

        client.add_event_listener(_on_event)

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
            status=ExecutionStatus.RUNNING,
            native_session_id=native_sess_id,
            process_id=client.pid,
            started_at=now,
            last_event_sequence=1,
            metadata=request.metadata,
        )

        with self._lock:
            self._active_handles[exec_id] = handle

        # If an initial prompt was provided, execute it asynchronously
        if request.prompt:
            def _async_prompt():
                try:
                    client.prompt(request.prompt, timeout=request.timeout_seconds)
                except Exception as exc:
                    with self._lock:
                        if exec_id in self._active_handles:
                            old = self._active_handles[exec_id]
                            self._active_handles[exec_id] = ExecutionHandle(
                                execution_id=old.execution_id,
                                request_id=old.request_id,
                                idempotency_key=old.idempotency_key,
                                task_id=old.task_id,
                                worker_id=old.worker_id,
                                worker_profile_version=old.worker_profile_version,
                                execution_generation=old.execution_generation,
                                provider=old.provider,
                                execution_mode=old.execution_mode,
                                workspace=old.workspace,
                                status=ExecutionStatus.FAILED,
                                native_session_id=old.native_session_id,
                                process_id=old.process_id,
                                started_at=old.started_at,
                                error_message=str(exc),
                                exit_code=1,
                            )

            t = threading.Thread(target=_async_prompt, name=f"pi-prompt-{exec_id}", daemon=True)
            t.start()

        return handle

    def prompt(self, execution_id: str, message: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Send a prompt turn to an active Pi session."""
        with self._lock:
            client = self._active_clients.get(execution_id)
        if not client:
            raise ExecutionNotFoundError(f"Active Pi execution '{execution_id}' not found.")
        return client.prompt(message, timeout=timeout or 300.0)

    def attach(self, execution_id: str) -> bool:
        with self._lock:
            client = self._active_clients.get(execution_id)
        return bool(client and client.is_alive)

    def resume(self, session_id: str, context: Optional[Any] = None) -> ExecutionHandle:
        """Resume an existing native Pi session."""
        bin_path = self.get_executable_path()
        if not bin_path:
            raise RuntimeError("Pi executable not found.")

        req_id = f"req-{uuid.uuid4().hex[:8]}"
        workspace = self._workspace_root or Path.cwd()
        client = PiRpcClient(
            executable_path=bin_path,
            workspace_path=workspace,
            session_id=session_id,
        )
        client.start()
        exec_id = f"exec-pi-resume-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        with self._lock:
            self._active_clients[exec_id] = client
            self._event_queues[exec_id] = []

        handle = ExecutionHandle(
            execution_id=exec_id,
            request_id=req_id,
            idempotency_key=req_id,
            task_id="resumed-task",
            worker_id="pi-worker",
            provider=self.name,
            workspace=str(workspace),
            status=ExecutionStatus.RUNNING,
            native_session_id=session_id,
            process_id=client.pid,
            started_at=now,
        )
        with self._lock:
            self._active_handles[exec_id] = handle
        return handle

    def inspect(self, execution_id: str) -> ExecutionHandle:
        with self._lock:
            handle = self._active_handles.get(execution_id)
            client = self._active_clients.get(execution_id)

        if not handle:
            raise ExecutionNotFoundError(f"Execution '{execution_id}' not found on Pi provider.")

        if client:
            alive = client.is_alive
            running = client.is_running
            new_status = handle.status
            if not alive:
                code = client.proc.poll() if client.proc else 0
                new_status = ExecutionStatus.COMPLETED if code == 0 else ExecutionStatus.FAILED
            elif running:
                new_status = ExecutionStatus.RUNNING
            else:
                new_status = ExecutionStatus.COMPLETED

            if new_status != handle.status:
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
                    status=new_status,
                    native_session_id=handle.native_session_id,
                    process_id=handle.process_id,
                    exit_code=client.proc.poll() if client.proc else 0,
                    started_at=handle.started_at,
                    completed_at=datetime.now(timezone.utc) if new_status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED] else None,
                    last_event_sequence=handle.last_event_sequence,
                    error_message=handle.error_message,
                    metadata=handle.metadata,
                )
                with self._lock:
                    self._active_handles[execution_id] = handle

        return handle

    def stream_events(self, execution_id: str) -> Iterator[ExecutionEvent]:
        with self._lock:
            events = list(self._event_queues.get(execution_id, []))
        for ev in events:
            yield ev

    def send_input(self, execution_id: str, message: str) -> bool:
        with self._lock:
            client = self._active_clients.get(execution_id)
        if not client:
            raise ExecutionNotFoundError(f"Active Pi execution '{execution_id}' not found.")
        try:
            client.send_command("prompt", {"message": message})
            return True
        except Exception:
            return False

    def stop(self, execution_id: str, force: bool = False) -> bool:
        with self._lock:
            client = self._active_clients.get(execution_id)
            handle = self._active_handles.get(execution_id)

        if not client:
            return False

        client.close(force=force)
        if handle:
            updated = ExecutionHandle(
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
                started_at=handle.started_at,
                completed_at=datetime.now(timezone.utc),
            )
            with self._lock:
                self._active_handles[execution_id] = updated
        return True

    def list_agents(self) -> List[Dict[str, Any]]:
        return list_pi_agents(self._home, self._workspace_root)

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        for a in self.list_agents():
            if a["id"] == agent_id:
                return a
        return None

    def create_agent(self, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_pi_agent(definition, self._home, self._workspace_root)

    def update_agent(self, agent_id: str, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_pi_agent(definition, self._home, self._workspace_root)

    def delete_agent(self, agent_id: str) -> bool:
        return delete_pi_agent(agent_id, self._home, self._workspace_root)

    def list_skills(self) -> List[Dict[str, Any]]:
        return list_pi_skills(self._home, self._workspace_root)

    def install_skill(self, skill: CanonicalSkill) -> bool:
        return install_pi_skill(skill, self._home, self._workspace_root)

    def remove_skill(self, skill_id: str) -> bool:
        return remove_pi_skill(skill_id, self._home, self._workspace_root)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return list_pi_sessions(self._home)

    def export_session(self, session_id: str) -> Optional[NormalizedSession]:
        return export_pi_session(session_id, self._home)

    def resume_session(self, session_id: str) -> bool:
        bin_path = get_pi_bin()
        if not bin_path:
            return False
        clean_id = session_id.removeprefix("pi:")
        sessions_dir = get_pi_sessions_dir()
        if sessions_dir.is_dir():
            for f in sessions_dir.rglob("*.jsonl"):
                if clean_id in f.stem or clean_id in f.name:
                    return True
        return False

    def validate(self, definition: CanonicalAgentDefinition) -> List[str]:
        return []

    def export_canonical_agent(self, agent_id: str) -> Optional[CanonicalAgentDefinition]:
        return None
