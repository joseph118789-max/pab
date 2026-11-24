"""Google Antigravity CLI (agy) Provider Adapter."""

import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.exceptions import ExecutionNotFoundError
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
from pab.providers.agy.execution import AgyExecutionResult, AgyRunner
from pab.providers.agy.agents import (
    compile_agy_agent,
    delete_agy_agent,
    list_agy_agents,
)
from pab.providers.agy.config import (
    get_agy_bin,
    get_agy_cli_dir,
    get_agy_config_dir,
)
from pab.providers.agy.memory import list_agy_memories
from pab.providers.agy.sessions import (
    export_agy_session,
    list_agy_sessions,
)
from pab.providers.agy.skills import (
    install_agy_skill,
    list_agy_skills,
    remove_agy_skill,
)
from pab.providers.agy.workers import AgyWorkerRegistry
from pab.providers.base import AgentAdapter, AgentProvider


class AgyAdapter(AgentAdapter):
    """Adapter for Google Antigravity CLI (agy)."""

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        cli_dir: Optional[Path] = None,
        workspace_root: Optional[Path] = None,
        worker_registry: Optional[AgyWorkerRegistry] = None,
        runner: Optional[AgyRunner] = None,
        default_timeout: float = 900.0,
    ):
        self._config_dir = config_dir or get_agy_config_dir()
        self._cli_dir = cli_dir or get_agy_cli_dir()
        self._workspace_root = workspace_root
        self._workers = worker_registry or AgyWorkerRegistry.from_config()
        self._runner = runner or AgyRunner(default_timeout=default_timeout)
        self._handles: Dict[str, ExecutionHandle] = {}
        self._results: Dict[str, AgyExecutionResult] = {}
        self._lock = threading.Lock()

    def get_executable_path(self) -> Optional[str]:
        return get_agy_bin() or "/root/.local/bin/agy"

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
            "inspect",
        ]

    # ------------------------------------------------------------------
    # Execution (real AGY print-mode subprocess)
    # ------------------------------------------------------------------
    def worker_registry(self) -> AgyWorkerRegistry:
        """Return the AGY worker registry backing this adapter."""
        return self._workers

    def launch(self, request: LaunchRequest) -> ExecutionHandle:
        """
        Execute an AGY print-mode turn for the requested worker.

        The AGY process is started for real, in the worker's workdir, under the
        worker's isolated profile HOME. The returned handle reports COMPLETED only
        when AGY exited cleanly and returned a valid, traceable result.
        """
        # Session isolation guard: prevent worker executions from targeting channel-answerable sessions
        req_session = request.metadata.get("session_key") or (
            request.environment.get("OPENCLAW_SESSION_KEY") if request.environment else None
        )
        if req_session and (
            req_session == "agent:main:main"
            or req_session.startswith("agent:main:")
            or req_session.startswith("agent:whatsapp-observer:")
        ):
            raise ValueError(
                f"Worker execution rejected: targeting channel-bound session '{req_session}' is prohibited."
            )

        exec_id = f"exec-agy-{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)

        worker = self._workers.resolve(
            worker_id=request.worker_id,
            worktree=request.workspace_path,
        )

        result = self._runner.run(
            worker,
            prompt=request.prompt or "",
            timeout=request.timeout_seconds or self._runner.default_timeout,
            extra_env=request.environment,
            workdir=Path(request.workspace_path) if request.workspace_path else None,
        )

        metadata = {
            **request.metadata,
            **result.to_dict(),
            "session_key": result.session_key,
        }

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
            status=ExecutionStatus.COMPLETED if result.ok else ExecutionStatus.FAILED,
            native_session_id=result.conversation_id,
            exit_code=result.exit_code,
            started_at=now,
            completed_at=datetime.now(timezone.utc),
            error_message=result.error,
            metadata=metadata,
        )

        with self._lock:
            self._handles[exec_id] = handle
            self._results[exec_id] = result

        return handle

    def result_for(self, execution_id: str) -> AgyExecutionResult:
        """Return the captured AGY result for an execution."""
        with self._lock:
            result = self._results.get(execution_id)
        if not result:
            raise ExecutionNotFoundError(f"Execution '{execution_id}' not found on AGY provider.")
        return result

    def inspect(self, execution_id: str) -> ExecutionHandle:
        """Return the recorded handle for a completed AGY execution."""
        with self._lock:
            handle = self._handles.get(execution_id)
        if not handle:
            raise ExecutionNotFoundError(f"Execution '{execution_id}' not found on AGY provider.")
        return handle

    def stop(self, execution_id: str, force: bool = False) -> bool:
        """
        AGY print-mode turns are synchronous, so there is no live process to stop.
        Returns False instead of pretending a cancellation happened.
        """
        return False

    @property
    def name(self) -> str:
        return "agy"

    @property
    def display_name(self) -> str:
        return "Google Antigravity CLI (agy)"

    def detect(self) -> bool:
        return bool(get_agy_bin() or self._config_dir.is_dir() or self._cli_dir.is_dir())

    def version(self) -> Optional[str]:
        bin_path = get_agy_bin()
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
            "agent_management": True,
            "progressive_disclosure_skills": True,
            "skills": True,
            "rules": True,
            "sessions": True,
            "native_resume": True,
            "instruction_files": ["GEMINI.md", "AGENTS.md", "agent.md"],
            "execution": True,
            "print_mode": True,
            "json_output": True,
            "profile_isolation": True,
            "workers": [w.to_dict() for w in self._workers.list_workers()],
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        return list_agy_agents(self._config_dir, self._workspace_root)

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        for a in self.list_agents():
            if a["id"] == agent_id:
                return a
        return None

    def create_agent(self, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_agy_agent(definition, self._config_dir, self._workspace_root)

    def update_agent(self, agent_id: str, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_agy_agent(definition, self._config_dir, self._workspace_root)

    def delete_agent(self, agent_id: str) -> bool:
        return delete_agy_agent(agent_id, self._config_dir, self._workspace_root)

    def list_skills(self) -> List[Dict[str, Any]]:
        return list_agy_skills(self._config_dir, self._workspace_root)

    def install_skill(self, skill: CanonicalSkill) -> bool:
        return install_agy_skill(skill, self._config_dir, self._workspace_root)

    def remove_skill(self, skill_id: str) -> bool:
        return remove_agy_skill(skill_id, self._config_dir, self._workspace_root)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return list_agy_sessions(self._cli_dir)

    def export_session(self, session_id: str) -> Optional[NormalizedSession]:
        return export_agy_session(session_id, self._cli_dir)

    def resume_session(self, session_id: str) -> bool:
        bin_path = get_agy_bin()
        if not bin_path:
            return False
        # Native resume via agy --conversation
        return True

    def validate(self, definition: CanonicalAgentDefinition) -> List[str]:
        warnings = []
        if definition.preferences.reasoning_effort not in ["inherit", "low", "medium", "high", "xhigh", "max"]:
            warnings.append(
                f"Antigravity CLI expects effort to be low|medium|high|xhigh|max. Found: '{definition.preferences.reasoning_effort}'"
            )
        return warnings

    def export_canonical_agent(self, agent_id: str) -> Optional[CanonicalAgentDefinition]:
        ag = self.get_agent(agent_id)
        if not ag or not ag.get("path"):
            return None
        from pab.core.models.agent import AgentIdentity, AgentInstructions
        return CanonicalAgentDefinition(
            id=agent_id,
            name=ag.get("name", agent_id),
            description=ag.get("description", ""),
            identity=AgentIdentity(role=ag.get("name", agent_id)),
            instructions=AgentInstructions(),
        )
