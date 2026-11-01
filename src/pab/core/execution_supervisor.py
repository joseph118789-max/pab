"""PAB Execution Supervisor Foundation.

Manages agent execution lifecycles, idempotency guards, event sequencing,
process termination, and restart reconciliation.
Does NOT manage PersonaOS task queues or workforce scheduling logic.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pab.core.capability_registry import CapabilityRegistry
from pab.core.config import ConfigManager
from pab.core.db import Database
from pab.core.exceptions import (
    DuplicateExecutionError,
    ExecutionNotFoundError,
    ProviderNotFoundError,
    StaleGenerationError,
    UnsupportedOperationError,
)
from pab.core.models.execution import (
    ExecutionEvent,
    ExecutionHandle,
    ExecutionMode,
    ExecutionStatus,
    LaunchRequest,
)
from pab.providers.base import AgentAdapter


class ExecutionSupervisor:
    """Supervises active agent executions and guarantees idempotency and event ordering."""

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        capability_registry: Optional[CapabilityRegistry] = None,
    ):
        self.config = config_manager or ConfigManager()
        self.db = Database(self.config.db_path)
        self.capabilities = capability_registry or CapabilityRegistry()
        self._running_processes: Dict[str, subprocess.Popen] = {}

    def launch(self, request: LaunchRequest) -> ExecutionHandle:
        """Launch an external agent with idempotency verification."""
        # 1. Idempotency check: return existing execution if already launched
        existing = self.db.get_execution_by_idempotency_key(request.idempotency_key)
        if existing:
            # If already active or completed, return the existing handle
            if existing.status in [ExecutionStatus.RUNNING, ExecutionStatus.STARTING, ExecutionStatus.COMPLETED]:
                return existing

        # 2. Provider verification
        caps = self.capabilities.get_capabilities(request.provider)
        if not caps:
            raise ProviderNotFoundError(f"Provider '{request.provider}' is not registered.")
        if not caps.available:
            raise RuntimeError(f"Provider '{request.provider}' is not installed or available on this host.")

        exec_id = f"exec-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        adapter = self.capabilities.provider_registry.get(request.provider)

        # 3. Mode dispatch: managed_process vs orca_terminal
        pid: Optional[int] = None
        term_handle: Optional[str] = None
        native_sess_id: Optional[str] = None
        status = ExecutionStatus.RUNNING
        err_msg: Optional[str] = None

        if (
            isinstance(adapter, AgentAdapter)
            and "launch" in adapter.supported_operations()
            and adapter.__class__.launch is not AgentAdapter.launch
        ):
            # Delegate to specialized adapter launch
            handle = adapter.launch(request)
            exec_id = handle.execution_id
            pid = handle.process_id
            term_handle = handle.terminal_handle
            native_sess_id = handle.native_session_id
            status = handle.status
        else:
            # Default process launcher for managed_process
            if request.execution_mode == ExecutionMode.MANAGED_PROCESS:
                cmd = request.command
                if not cmd:
                    exe = caps.executable_path or request.provider
                    cmd = [exe]
                    if request.prompt:
                        cmd.extend(["-p", request.prompt])

                # Argument array invocation (no shell=True)
                if isinstance(cmd, str):
                    import shlex
                    cmd_args = shlex.split(cmd)
                else:
                    cmd_args = list(cmd)

                env = os.environ.copy()
                env.update(request.environment)

                try:
                    proc = subprocess.Popen(
                        cmd_args,
                        cwd=str(request.workspace_path) if request.workspace_path.is_dir() else None,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    pid = proc.pid
                    self._running_processes[exec_id] = proc
                except Exception as exc:
                    status = ExecutionStatus.FAILED
                    err_msg = str(exc)

            elif request.execution_mode == ExecutionMode.ORCA_TERMINAL:
                term_handle = f"term_orca_{uuid.uuid4().hex[:8]}"

        # 4. Construct execution handle
        handle = ExecutionHandle(
            execution_id=exec_id,
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            task_id=request.task_id,
            worker_id=request.worker_id,
            worker_profile_version=request.worker_profile_version,
            execution_generation=request.execution_generation,
            provider=request.provider,
            execution_mode=request.execution_mode,
            workspace=str(request.workspace_path),
            status=status,
            native_session_id=native_sess_id,
            process_id=pid,
            terminal_handle=term_handle,
            exit_code=None if status != ExecutionStatus.FAILED else 1,
            started_at=now,
            last_event_sequence=1,
            error_message=err_msg,
            metadata=request.metadata,
        )

        # 5. Persist execution and emit initial event
        self.db.save_execution(handle)
        start_event = ExecutionEvent(
            event_id=f"evt-{uuid.uuid4().hex[:10]}",
            execution_id=exec_id,
            request_id=request.request_id,
            execution_generation=request.execution_generation,
            sequence_number=1,
            event_type="execution.started" if status != ExecutionStatus.FAILED else "execution.failed",
            timestamp=now,
            payload={
                "provider": request.provider,
                "process_id": pid,
                "terminal_handle": term_handle,
                "error": err_msg,
            },
        )
        self.db.save_event(start_event)
        return handle

    def get_execution(self, execution_id: str) -> ExecutionHandle:
        """Fetch current execution status and check live process health."""
        handle = self.db.get_execution(execution_id)
        if not handle:
            raise ExecutionNotFoundError(f"Execution '{execution_id}' does not exist.")

        # If in running state and managed_process, inspect process status
        if handle.status == ExecutionStatus.RUNNING and handle.execution_mode == ExecutionMode.MANAGED_PROCESS:
            proc = self._running_processes.get(execution_id)
            if proc:
                poll = proc.poll()
                if poll is not None:
                    # Process completed
                    new_status = ExecutionStatus.COMPLETED if poll == 0 else ExecutionStatus.FAILED
                    completed_at = datetime.now(timezone.utc)
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
                        terminal_handle=handle.terminal_handle,
                        exit_code=poll,
                        started_at=handle.started_at,
                        completed_at=completed_at,
                        last_event_sequence=handle.last_event_sequence + 1,
                        error_message=None if poll == 0 else f"Process exited with code {poll}",
                        metadata=handle.metadata,
                    )
                    self.db.update_execution(handle)
                    self.emit_event(
                        execution_id=execution_id,
                        event_type="execution.completed" if poll == 0 else "execution.failed",
                        payload={"exit_code": poll},
                        generation=handle.execution_generation,
                        request_id=handle.request_id,
                    )
            elif handle.process_id:
                # Check OS PID if process object not cached in memory
                try:
                    os.kill(handle.process_id, 0)
                except OSError:
                    # Process no longer exists
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
                        status=ExecutionStatus.INTERRUPTED,
                        native_session_id=handle.native_session_id,
                        process_id=handle.process_id,
                        terminal_handle=handle.terminal_handle,
                        exit_code=137,
                        started_at=handle.started_at,
                        completed_at=datetime.now(timezone.utc),
                        last_event_sequence=handle.last_event_sequence + 1,
                        error_message="Process terminated unexpectedly",
                        metadata=handle.metadata,
                    )
                    self.db.update_execution(handle)
                    self.emit_event(
                        execution_id=execution_id,
                        event_type="execution.interrupted",
                        payload={"reason": "OS process disappeared"},
                        generation=handle.execution_generation,
                        request_id=handle.request_id,
                    )

        return handle

    def stop(self, execution_id: str, force: bool = False) -> ExecutionHandle:
        """Terminate an active execution and record cancellation."""
        handle = self.get_execution(execution_id)
        if handle.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
            return handle

        # Stop adapter if specialized
        adapter = self.capabilities.provider_registry.get(handle.provider)
        if (
            isinstance(adapter, AgentAdapter)
            and "stop" in adapter.supported_operations()
            and adapter.__class__.stop is not AgentAdapter.stop
        ):
            adapter.stop(execution_id, force=force)

        # Stop local process
        proc = self._running_processes.get(execution_id)
        if proc:
            try:
                if force:
                    proc.kill()
                else:
                    proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
        elif handle.process_id:
            try:
                sig = signal.SIGKILL if force else signal.SIGTERM
                os.kill(handle.process_id, sig)
            except OSError:
                pass

        now = datetime.now(timezone.utc)
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
            terminal_handle=handle.terminal_handle,
            exit_code=137 if force else 130,
            started_at=handle.started_at,
            completed_at=now,
            last_event_sequence=handle.last_event_sequence + 1,
            error_message="Execution cancelled by operator",
            metadata=handle.metadata,
        )
        self.db.update_execution(updated)
        self.emit_event(
            execution_id=execution_id,
            event_type="execution.cancelled",
            payload={"force": force},
            generation=handle.execution_generation,
            request_id=handle.request_id,
        )
        return updated

    def emit_event(
        self,
        execution_id: str,
        event_type: str,
        payload: Dict[str, Any],
        generation: int,
        request_id: Optional[str] = None,
    ) -> ExecutionEvent:
        """Emit a durable, ordered event with execution generation fencing check."""
        handle = self.db.get_execution(execution_id)
        if not handle:
            raise ExecutionNotFoundError(f"Execution '{execution_id}' does not exist.")

        # Stale generation check
        if generation != handle.execution_generation:
            raise StaleGenerationError(
                f"Event generation {generation} does not match current execution generation {handle.execution_generation}"
            )

        seq = self.db.get_next_sequence_number(execution_id)
        event = ExecutionEvent(
            event_id=f"evt-{uuid.uuid4().hex[:10]}",
            execution_id=execution_id,
            request_id=request_id or handle.request_id,
            execution_generation=generation,
            sequence_number=seq,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            payload=payload,
        )
        self.db.save_event(event)
        return event

    def list_events(self, execution_id: str, since_sequence: int = 0) -> List[ExecutionEvent]:
        """Fetch sequenced event trail for an execution."""
        return self.db.list_events(execution_id, since_sequence=since_sequence)

    def reconcile_executions(self) -> int:
        """PAB restart reconciliation: inspect active executions and mark dead PIDs as interrupted."""
        active = self.db.list_executions(status=ExecutionStatus.RUNNING.value)
        reconciled = 0
        now = datetime.now(timezone.utc)

        for handle in active:
            if handle.execution_mode == ExecutionMode.MANAGED_PROCESS and handle.process_id:
                alive = True
                try:
                    os.kill(handle.process_id, 0)
                except OSError:
                    alive = False

                if not alive:
                    reconciled += 1
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
                        status=ExecutionStatus.INTERRUPTED,
                        native_session_id=handle.native_session_id,
                        process_id=handle.process_id,
                        terminal_handle=handle.terminal_handle,
                        exit_code=137,
                        started_at=handle.started_at,
                        completed_at=now,
                        last_event_sequence=handle.last_event_sequence + 1,
                        error_message="Process died during PAB restart or crash",
                        metadata=handle.metadata,
                    )
                    self.db.update_execution(updated)
                    self.emit_event(
                        execution_id=handle.execution_id,
                        event_type="execution.interrupted",
                        payload={"reconciled_after_restart": True},
                        generation=handle.execution_generation,
                        request_id=handle.request_id,
                    )
        return reconciled
