"""Universal Agent Orchestration Engine.

Coordinates multi-agent workflows across OpenAI Codex, Anthropic Claude Code,
Google Antigravity (agy), OpenClaw, and Pi Coding Agent.
Adopts Orca ADE orchestration primitives (Runs, Tasks, Dispatches, Decision Gates, Messages)
while strictly adhering to PersonaOS kernel authority.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pab.core.capability_registry import CapabilityRegistry
from pab.core.config import ConfigManager
from pab.core.db import Database
from pab.core.exceptions import PABError, ProviderExecutionError, UnsupportedOperationError
from pab.core.execution_supervisor import ExecutionSupervisor
from pab.core.models.execution import ExecutionMode, ExecutionStatus, LaunchRequest
from pab.core.models.orchestration import (
    DecisionGate,
    DispatchStatus,
    GateStatus,
    OrchestrationDispatch,
    OrchestrationMessage,
    OrchestrationRun,
    OrchestrationTask,
    RunStatus,
    TaskStatus,
)
from pab.core.orca_bridge import OrcaBridge
from pab.providers.agy.workers import AgyWorkerResolutionError
from pab.providers.detector import ProviderRegistry
from pab.providers.pi.adapter import PiAdapter

# Providers with a real, verified execution implementation. Every other provider
# fails explicitly instead of reporting a fabricated success.
EXECUTABLE_DISPATCH_PROVIDERS = ("agy", "pi")

logger = logging.getLogger("pab.core.orchestration")


class OrchestrationEngine:
    """Universal multi-agent control plane engine."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config = config_manager or ConfigManager()
        self.db = Database(self.config.db_path)
        self.providers = ProviderRegistry(workspace_root=self.config.root.parent)
        self.orca = OrcaBridge()

    # -------------------------------------------------------------------------
    # Run Management
    # -------------------------------------------------------------------------
    def create_run(
        self,
        name: str,
        objective: str,
        workspace_path: Optional[Path] = None,
        coordinator_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrchestrationRun:
        """Create a new orchestration Run boundary and inbox."""
        ws = str(Path(workspace_path).resolve()) if workspace_path else str(Path.cwd().resolve())
        run_id = f"run-{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)

        meta = dict(metadata or {})
        # If Orca is running on host, try binding an Orca run
        if self.orca.is_available:
            try:
                orca_res = self.orca.create_run(objective)
                if orca_res and "id" in orca_res:
                    meta["orca_run_id"] = orca_res["id"]
            except Exception as e:
                logger.debug("Orca run creation skipped: %s", e)

        run = OrchestrationRun(
            run_id=run_id,
            name=name,
            objective=objective,
            workspace_path=ws,
            status=RunStatus.ACTIVE,
            coordinator_agent=coordinator_agent,
            created_at=now,
            metadata=meta,
        )
        self.db.save_run(run)
        return run

    def get_run(self, run_id: str) -> Optional[OrchestrationRun]:
        return self.db.get_run(run_id)

    def list_runs(self, status: Optional[str] = None) -> List[OrchestrationRun]:
        return self.db.list_runs(status)

    # -------------------------------------------------------------------------
    # Task Management
    # -------------------------------------------------------------------------
    def create_task(
        self,
        run_id: str,
        title: str,
        spec: str,
        dependencies: Optional[List[str]] = None,
        worker_id: Optional[str] = None,
        personaos_task_id: Optional[str] = None,
    ) -> OrchestrationTask:
        """Create an orchestration task linked to a PersonaOS task ID."""
        run = self.get_run(run_id)
        if not run:
            raise PABError(f"Orchestration Run '{run_id}' not found.")

        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = OrchestrationTask(
            task_id=task_id,
            run_id=run_id,
            title=title,
            spec=spec,
            dependencies=dependencies or [],
            status=TaskStatus.PENDING,
            assigned_worker_id=worker_id,
            personaos_task_id=personaos_task_id or task_id,
            created_at=datetime.now(timezone.utc),
        )
        self.db.save_task(task)
        return task

    def get_task(self, task_id: str) -> Optional[OrchestrationTask]:
        return self.db.get_task(task_id)

    def list_tasks(self, run_id: Optional[str] = None) -> List[OrchestrationTask]:
        return self.db.list_tasks(run_id)

    # -------------------------------------------------------------------------
    # Decision Gates
    # -------------------------------------------------------------------------
    def create_decision_gate(
        self,
        task_id: str,
        question: str,
        options: Optional[List[str]] = None,
    ) -> DecisionGate:
        """Create a blocking decision gate for a task."""
        task = self.get_task(task_id)
        if not task:
            raise PABError(f"Task '{task_id}' not found.")

        gate_id = f"gate-{uuid.uuid4().hex[:8]}"
        gate = DecisionGate(
            gate_id=gate_id,
            task_id=task_id,
            question=question,
            options=options or ["approve", "reject"],
            status=GateStatus.PENDING,
        )
        self.db.save_decision_gate(gate)

        # Mark task as BLOCKED
        blocked_task = OrchestrationTask(
            task_id=task.task_id,
            run_id=task.run_id,
            title=task.title,
            spec=task.spec,
            dependencies=task.dependencies,
            status=TaskStatus.BLOCKED,
            assigned_worker_id=task.assigned_worker_id,
            gate_id=gate_id,
            personaos_task_id=task.personaos_task_id,
            created_at=task.created_at,
        )
        self.db.save_task(blocked_task)
        return gate

    def resolve_decision_gate(
        self,
        gate_id: str,
        choice: str,
        resolved_by: str = "human",
    ) -> DecisionGate:
        """Resolve a decision gate and update the blocked task status."""
        gate = self.db.get_decision_gate(gate_id)
        if not gate:
            raise PABError(f"Decision gate '{gate_id}' not found.")

        if choice not in gate.options:
            raise PABError(f"Invalid choice '{choice}'. Must be one of: {gate.options}")

        now = datetime.now(timezone.utc)
        resolved_gate = DecisionGate(
            gate_id=gate.gate_id,
            task_id=gate.task_id,
            question=gate.question,
            options=gate.options,
            status=GateStatus.RESOLVED,
            resolution=choice,
            resolved_by=resolved_by,
            resolved_at=now,
        )
        self.db.save_decision_gate(resolved_gate)

        # Update task status
        task = self.get_task(gate.task_id)
        if task:
            new_status = TaskStatus.PENDING if choice in ["approve", "yes", gate.options[0]] else TaskStatus.FAILED
            updated_task = OrchestrationTask(
                task_id=task.task_id,
                run_id=task.run_id,
                title=task.title,
                spec=task.spec,
                dependencies=task.dependencies,
                status=new_status,
                assigned_worker_id=task.assigned_worker_id,
                gate_id=None if new_status == TaskStatus.PENDING else task.gate_id,
                personaos_task_id=task.personaos_task_id,
                created_at=task.created_at,
            )
            self.db.save_task(updated_task)

        return resolved_gate

    # -------------------------------------------------------------------------
    # Task Dispatch & Multi-Agent Execution
    # -------------------------------------------------------------------------
    def dispatch_task(
        self,
        run_id: str,
        task_id: str,
        agent_provider: str,
        worker_id: Optional[str] = None,
        worktree_path: Optional[Path] = None,
        spec_override: Optional[str] = None,
        dry_run: bool = False,
        timeout_seconds: float = 900.0,
    ) -> OrchestrationDispatch:
        """Dispatch a task to a target agent runtime in an isolated workspace."""
        run = self.get_run(run_id)
        if not run:
            raise PABError(f"Run '{run_id}' not found.")

        task = self.get_task(task_id)
        if not task:
            raise PABError(f"Task '{task_id}' not found.")

        # Gate Check: Prevent dispatch if task is blocked by a pending decision gate
        if task.status == TaskStatus.BLOCKED and task.gate_id:
            gate = self.db.get_decision_gate(task.gate_id)
            if gate and gate.status == GateStatus.PENDING:
                raise PABError(
                    f"Task '{task_id}' cannot be dispatched: blocked by pending Decision Gate '{gate.gate_id}' ('{gate.question}'). "
                    f"Resolve it first with: pab run gate resolve --gate {gate.gate_id} --choice <option>"
                )

        provider_key = agent_provider.lower()
        provider = self.providers.get(provider_key)
        if not provider:
            raise PABError(f"Agent provider '{agent_provider}' not registered.")

        # Only providers with a real, verified execution implementation may be
        # dispatched. Everything else fails loudly instead of faking a success.
        if provider_key not in EXECUTABLE_DISPATCH_PROVIDERS:
            raise UnsupportedOperationError(
                f"Provider '{provider_key}' does not support execution dispatch. "
                f"Implemented dispatch targets: {', '.join(EXECUTABLE_DISPATCH_PROVIDERS)}."
            )

        dispatch_id = f"disp-{uuid.uuid4().hex[:8]}"
        requested_worker = worker_id or task.assigned_worker_id
        resolved_worker = requested_worker or f"personaos-{provider_key}"
        resolved_spec = spec_override or task.spec

        # AGY workers are bound to an isolated profile: resolve the worker (and its
        # working directory) before the dispatch so the right profile is used.
        agy_worker = None
        if provider_key == "agy":
            agy_worker = self._resolve_agy_worker(requested_worker, worktree_path)
            if agy_worker is not None:
                resolved_worker = agy_worker.worker_id
            else:
                raise AgyWorkerResolutionError(
                    "AGY dispatch requires a known worker. "
                    f"Pass --worker <id> or a --worktree inside a worker directory. "
                    f"Known workers: {', '.join(w.worker_id for w in self._agy_workers())}."
                )

        worktree = self._resolve_worktree(run, worktree_path, provider_key, resolved_worker, agy_worker)

        now = datetime.now(timezone.utc)
        dispatch_status = DispatchStatus.RUNNING
        pid: Optional[int] = None
        term_handle: Optional[str] = None
        result_text: Optional[str] = None
        task_status = TaskStatus.DISPATCHED
        extra_metadata: Dict[str, Any] = {}

        if dry_run:
            dispatch_status = DispatchStatus.SETTLED
            plan = self._describe_dispatch_plan(provider_key, resolved_worker, worktree, resolved_spec)
            extra_metadata["dry_run"] = True
            extra_metadata["plan"] = plan
            result_text = f"[Dry Run] Would dispatch '{task.title}' to {provider.display_name} in {worktree}"
            task_status = TaskStatus.PENDING
        else:
            handle = self._execute_dispatch(
                provider_key=provider_key,
                dispatch_id=dispatch_id,
                task_id=task_id,
                worker_id=resolved_worker,
                worktree=worktree,
                spec=resolved_spec,
                timeout_seconds=timeout_seconds,
                run=run,
            )
            pid = handle.process_id
            term_handle = handle.terminal_handle
            extra_metadata["execution_id"] = handle.execution_id
            extra_metadata.update(handle.metadata or {})

            if handle.status == ExecutionStatus.COMPLETED:
                dispatch_status = DispatchStatus.SETTLED
                task_status = TaskStatus.COMPLETED
                result_text = self._summarise_success(provider_key, task.title, handle)
            elif handle.status == ExecutionStatus.RUNNING:
                # Execution accepted but still running: not completed.
                dispatch_status = DispatchStatus.RUNNING
                task_status = TaskStatus.DISPATCHED
                result_text = (
                    f"{provider.display_name} accepted '{task.title}' and is still running "
                    f"(execution {handle.execution_id})."
                )
            else:
                dispatch_status = DispatchStatus.FAILED
                task_status = TaskStatus.FAILED
                result_text = f"{provider.display_name} failed to execute '{task.title}': {handle.error_message or 'unknown error'}"

            if dispatch_status == DispatchStatus.SETTLED:
                # Bridge completion to Orca Run if active
                if self.orca.is_available and "orca_run_id" in run.metadata:
                    try:
                        self.orca.send_worker_done(
                            run_id=run.metadata["orca_run_id"],
                            task_id=task_id,
                            dispatch_id=dispatch_id,
                            outcome="succeeded",
                        )
                    except Exception as exc:
                        logger.warning("Failed to bridge worker_done to Orca: %s", exc)

        dispatch = OrchestrationDispatch(
            dispatch_id=dispatch_id,
            task_id=task_id,
            run_id=run_id,
            agent_provider=provider_key,
            worker_id=resolved_worker,
            worktree_path=str(worktree),
            status=dispatch_status,
            terminal_handle=term_handle,
            process_id=pid,
            started_at=now,
            completed_at=now if dispatch_status in [DispatchStatus.SETTLED, DispatchStatus.COMPLETED, DispatchStatus.FAILED] else None,
            result_summary=result_text,
            metadata={"objective": run.objective, "spec": resolved_spec, **extra_metadata},
        )
        self.db.save_dispatch(dispatch)

        # Task lifecycle: only a verified execution may mark the task completed.
        updated_task = OrchestrationTask(
            task_id=task.task_id,
            run_id=task.run_id,
            title=task.title,
            spec=task.spec,
            dependencies=task.dependencies,
            status=task_status,
            assigned_worker_id=resolved_worker,
            gate_id=task.gate_id,
            personaos_task_id=task.personaos_task_id,
            created_at=task.created_at,
        )
        self.db.save_task(updated_task)

        return dispatch

    # ------------------------------------------------------------------
    # Dispatch helpers
    # ------------------------------------------------------------------
    def _agy_registry(self):
        """Return the AGY worker registry bound to the AGY adapter (if any)."""
        provider = self.providers.get("agy")
        registry = getattr(provider, "worker_registry", None)
        if callable(registry):
            try:
                return registry()
            except Exception:
                return None
        return registry

    def _agy_workers(self):
        registry = self._agy_registry()
        if registry is None:
            return []
        return registry.list_workers()

    def _resolve_agy_worker(self, requested_worker: Optional[str], worktree_path: Optional[Path]):
        """
        Resolve the AGY worker for a dispatch.

        An explicitly requested worker id must exist. When no worker id is given the
        worker is derived from the worktree (absolute paths are matched against the
        known worker directories).
        """
        registry = self._agy_registry()
        if registry is None:
            return None

        if requested_worker:
            worker = registry.get(requested_worker)
            if worker:
                return worker
            raise AgyWorkerResolutionError(
                f"Unknown AGY worker '{requested_worker}'. "
                f"Known workers: {', '.join(w.worker_id for w in registry.list_workers())}."
            )

        if worktree_path is not None:
            return registry.resolve(worktree=Path(worktree_path).expanduser())

        return None

    def _resolve_worktree(
        self,
        run: OrchestrationRun,
        worktree_path: Optional[Path],
        provider_key: str,
        worker_id: str,
        agy_worker: Any = None,
    ) -> Path:
        """
        Resolve the working directory for a dispatch.

        Absolute paths are used verbatim (only normalised); relative paths are
        resolved against the run workspace so that the recorded worktree is always
        an absolute path. For AGY, an unspecified worktree resolves to the
        worker's own directory so that profile isolation is preserved.
        """
        if worktree_path is not None:
            candidate = Path(worktree_path).expanduser()
            if not candidate.is_absolute():
                candidate = Path(run.workspace_path).expanduser() / candidate
            return candidate.resolve()

        if provider_key == "agy" and agy_worker is not None:
            return Path(agy_worker.workdir).expanduser().resolve()

        return Path(run.workspace_path).expanduser().resolve()

    def _execute_dispatch(
        self,
        provider_key: str,
        dispatch_id: str,
        task_id: str,
        worker_id: str,
        worktree: Path,
        spec: str,
        timeout_seconds: float,
        run: OrchestrationRun,
    ):
        """Execute a dispatch through the supervised provider adapter."""
        supervisor = ExecutionSupervisor(self.config, CapabilityRegistry(self.providers))
        launch_req = LaunchRequest(
            request_id=f"req-{dispatch_id}",
            idempotency_key=f"idem-{dispatch_id}",
            worker_id=worker_id,
            task_id=task_id,
            provider=provider_key,
            workspace_path=worktree,
            prompt=spec,
            execution_mode=ExecutionMode.MANAGED_PROCESS,
            timeout_seconds=timeout_seconds,
            metadata={
                "objective": run.objective,
                "spec": spec,
                "dispatch_id": dispatch_id,
            },
        )
        return supervisor.launch(launch_req)

    def _describe_dispatch_plan(
        self,
        provider_key: str,
        worker_id: str,
        worktree: Path,
        spec: str,
    ) -> Dict[str, Any]:
        """Describe what a real dispatch would do (no execution)."""
        plan: Dict[str, Any] = {
            "provider": provider_key,
            "worker_id": worker_id,
            "workdir": str(worktree),
            "spec": spec,
        }
        if provider_key == "agy":
            registry = self._agy_registry()
            if registry is not None:
                try:
                    worker = registry.resolve(worker_id=worker_id, worktree=worktree)
                    plan["worker"] = worker.worker_id
                    plan["profile"] = worker.profile
                    plan["profile_home"] = str(worker.profile_home)
                except Exception as exc:
                    plan["resolution_error"] = str(exc)
        return plan

    @staticmethod
    def _summarise_success(provider_key: str, task_title: str, handle) -> str:
        """Build a result summary from the verified execution result."""
        meta = handle.metadata or {}
        parts = [f"{provider_key.upper()} completed '{task_title}'"]
        if meta.get("profile"):
            parts.append(f"profile={meta['profile']}")
        if meta.get("conversation_id"):
            parts.append(f"conversation={meta['conversation_id']}")
        if meta.get("duration_seconds") is not None:
            parts.append(f"duration={meta['duration_seconds']}s")
        response = (meta.get("response") or "").strip()
        if response:
            excerpt = response if len(response) <= 500 else response[:500] + "..."
            parts.append(f"response={excerpt}")
        return " | ".join(parts)

    # -------------------------------------------------------------------------
    # Results Aggregation (Use Cases B & C)
    # -------------------------------------------------------------------------
    def get_run_results(self, run_id: str) -> Dict[str, Any]:
        """Synthesize all task dispatches into a unified cross-agent report."""
        run = self.get_run(run_id)
        if not run:
            raise PABError(f"Run '{run_id}' not found.")

        tasks = self.list_tasks(run_id)
        dispatches = self.db.list_dispatches(run_id=run_id)

        # Build markdown report
        lines = [
            f"# PAB Multi-Agent Orchestration Synthesis Report",
            f"",
            f"**Run ID:** `{run.run_id}`  ",
            f"**Name:** {run.name}  ",
            f"**Objective:** {run.objective}  ",
            f"**Status:** {run.status.value.upper()}  ",
            f"**Workspace:** `{run.workspace_path}`  ",
            f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
            f"",
            f"## 1. Dispatched Agent Findings",
            f"",
        ]

        if not dispatches:
            lines.append("_No agent dispatches recorded for this run._")
        else:
            for d in dispatches:
                t = next((tk for tk in tasks if tk.task_id == d.task_id), None)
                task_title = t.title if t else d.task_id
                st_icon = "✅" if d.status in [DispatchStatus.SETTLED, DispatchStatus.COMPLETED] else "❌"
                lines.append(f"### {st_icon} {d.agent_provider.upper()} — {task_title}")
                lines.append(f"- **Dispatch ID:** `{d.dispatch_id}`")
                lines.append(f"- **Worker Identity:** `{d.worker_id}`")
                lines.append(f"- **Status:** `{d.status.value}`")
                lines.append(f"- **Worktree:** `{d.worktree_path}`")
                dmeta = d.metadata or {}
                if dmeta.get("profile"):
                    lines.append(f"- **AGY Profile:** `{dmeta['profile']}` (`{dmeta.get('profile_home', 'n/a')}`)")
                if dmeta.get("conversation_id"):
                    lines.append(f"- **Trace ID:** `{dmeta['conversation_id']}`")
                if dmeta.get("trace_path"):
                    lines.append(f"- **Trace File:** `{dmeta['trace_path']}`")
                if dmeta.get("execution_id"):
                    lines.append(f"- **Execution ID:** `{dmeta['execution_id']}`")
                lines.append(f"- **Summary:** {d.result_summary or 'No summary recorded.'}")
                lines.append("")

        lines.extend([
            f"## 2. Task Completion Summary",
            f"",
            f"- Total Tasks: {len(tasks)}",
            f"- Completed: {sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)}",
            f"- Blocked by Gate: {sum(1 for t in tasks if t.status == TaskStatus.BLOCKED)}",
            f"- Pending: {sum(1 for t in tasks if t.status == TaskStatus.PENDING)}",
        ])

        report_md = "\n".join(lines)
        return {
            "run_id": run.run_id,
            "name": run.name,
            "objective": run.objective,
            "status": run.status.value,
            "total_tasks": len(tasks),
            "total_dispatches": len(dispatches),
            "report_markdown": report_md,
            "tasks": [t.to_dict() for t in tasks],
            "dispatches": [d.to_dict() for d in dispatches],
        }

    # -------------------------------------------------------------------------
    # Inter-Agent Messaging
    # -------------------------------------------------------------------------
    def send_message(
        self,
        run_id: str,
        subject: str,
        body: Optional[str] = None,
        msg_type: str = "status",
        from_handle: str = "coordinator",
        to_target: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> OrchestrationMessage:
        """Send an orchestration message and log in database."""
        msg_id = f"msg-{uuid.uuid4().hex[:10]}"
        msg = OrchestrationMessage(
            message_id=msg_id,
            run_id=run_id,
            subject=subject,
            body=body,
            msg_type=msg_type,
            from_handle=from_handle,
            to_target=to_target,
            payload=payload or {},
            timestamp=datetime.now(timezone.utc),
        )
        self.db.save_message(msg)

        if self.orca.is_available:
            self.orca.send_message(
                subject=subject,
                run_id=run_id,
                msg_type=msg_type,
                body=body,
                to_target=to_target,
            )

        return msg

    def list_messages(self, run_id: Optional[str] = None) -> List[OrchestrationMessage]:
        return self.db.list_messages(run_id)
