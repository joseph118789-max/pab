"""PAB Execution and Supervision Data Models.

Defines normalized contracts for agent execution, idempotency, lifecycle events,
and provider capabilities.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ExecutionMode(StrEnum):
    """Execution runtime hosting mode."""
    MANAGED_PROCESS = "managed_process"  # PAB directly launches and supervises OS process
    ORCA_TERMINAL = "orca_terminal"      # Orca hosts the terminal/PTY; PAB coordinates


class ExecutionStatus(StrEnum):
    """Normalized lifecycle states for an external agent execution."""
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LaunchRequest:
    """Idempotent worker execution request dispatched to PAB."""
    request_id: str
    idempotency_key: str
    worker_id: str
    task_id: str
    provider: str
    workspace_path: Path
    worker_profile_version: int = 1
    execution_generation: int = 1
    execution_mode: ExecutionMode = ExecutionMode.MANAGED_PROCESS
    timeout_seconds: float = 300.0
    contract_version: str = "1.0"
    command: Optional[str] = None
    prompt: Optional[str] = None
    model: Optional[str] = None
    effort: Optional[str] = None
    system_prompt: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "worker_id": self.worker_id,
            "worker_profile_version": self.worker_profile_version,
            "task_id": self.task_id,
            "execution_generation": self.execution_generation,
            "provider": self.provider,
            "workspace_path": str(self.workspace_path),
            "execution_mode": self.execution_mode.value,
            "timeout_seconds": self.timeout_seconds,
            "command": self.command,
            "prompt": self.prompt,
            "model": self.model,
            "effort": self.effort,
            "system_prompt": self.system_prompt,
            "skills": self.skills,
            "permissions": self.permissions,
            "environment": self.environment,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LaunchRequest:
        raw_mode = data.get("execution_mode", ExecutionMode.MANAGED_PROCESS.value)
        mode = ExecutionMode(raw_mode) if raw_mode in [m.value for m in ExecutionMode] else ExecutionMode.MANAGED_PROCESS
        return cls(
            contract_version=data.get("contract_version", "1.0"),
            request_id=data["request_id"],
            idempotency_key=data.get("idempotency_key") or data["request_id"],
            worker_id=data["worker_id"],
            worker_profile_version=int(data.get("worker_profile_version", 1)),
            task_id=data["task_id"],
            execution_generation=int(data.get("execution_generation", 1)),
            provider=data["provider"],
            workspace_path=Path(data["workspace_path"]),
            execution_mode=mode,
            timeout_seconds=float(data.get("timeout_seconds", 300.0)),
            command=data.get("command"),
            prompt=data.get("prompt"),
            model=data.get("model"),
            effort=data.get("effort"),
            system_prompt=data.get("system_prompt"),
            skills=data.get("skills", []),
            permissions=data.get("permissions", []),
            environment=data.get("environment", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class ExecutionHandle:
    """Normalized tracking reference for an active or completed execution."""
    execution_id: str
    request_id: str
    idempotency_key: str
    task_id: str
    worker_id: str
    provider: str
    workspace: str
    status: ExecutionStatus
    started_at: datetime
    worker_profile_version: int = 1
    execution_generation: int = 1
    execution_mode: ExecutionMode = ExecutionMode.MANAGED_PROCESS
    native_session_id: Optional[str] = None
    process_id: Optional[int] = None
    terminal_handle: Optional[str] = None
    exit_code: Optional[int] = None
    completed_at: Optional[datetime] = None
    last_event_sequence: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "worker_profile_version": self.worker_profile_version,
            "execution_generation": self.execution_generation,
            "provider": self.provider,
            "execution_mode": self.execution_mode.value,
            "workspace": self.workspace,
            "status": self.status.value,
            "native_session_id": self.native_session_id,
            "process_id": self.process_id,
            "terminal_handle": self.terminal_handle,
            "exit_code": self.exit_code,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_event_sequence": self.last_event_sequence,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionHandle:
        raw_mode = data.get("execution_mode", ExecutionMode.MANAGED_PROCESS.value)
        mode = ExecutionMode(raw_mode) if raw_mode in [m.value for m in ExecutionMode] else ExecutionMode.MANAGED_PROCESS
        raw_status = data["status"]
        status = ExecutionStatus(raw_status) if raw_status in [s.value for s in ExecutionStatus] else ExecutionStatus.UNKNOWN
        started_at = datetime.fromisoformat(data["started_at"]) if isinstance(data["started_at"], str) else data["started_at"]
        completed_at = None
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"]) if isinstance(data["completed_at"], str) else data["completed_at"]

        return cls(
            execution_id=data["execution_id"],
            request_id=data["request_id"],
            idempotency_key=data.get("idempotency_key", data["request_id"]),
            task_id=data["task_id"],
            worker_id=data["worker_id"],
            worker_profile_version=int(data.get("worker_profile_version", 1)),
            execution_generation=int(data.get("execution_generation", 1)),
            provider=data["provider"],
            execution_mode=mode,
            workspace=data["workspace"],
            status=status,
            native_session_id=data.get("native_session_id"),
            process_id=data.get("process_id"),
            terminal_handle=data.get("terminal_handle"),
            exit_code=data.get("exit_code"),
            started_at=started_at,
            completed_at=completed_at,
            last_event_sequence=int(data.get("last_event_sequence", 0)),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class ExecutionEvent:
    """Durable, sequenced lifecycle event for execution tracking."""
    event_id: str
    execution_id: str
    request_id: str
    execution_generation: int
    sequence_number: int
    event_type: str
    timestamp: datetime
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "execution_generation": self.execution_generation,
            "sequence_number": self.sequence_number,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionEvent:
        ts = datetime.fromisoformat(data["timestamp"]) if isinstance(data["timestamp"], str) else data["timestamp"]
        return cls(
            event_id=data["event_id"],
            execution_id=data["execution_id"],
            request_id=data["request_id"],
            execution_generation=int(data["execution_generation"]),
            sequence_number=int(data["sequence_number"]),
            event_type=data["event_type"],
            timestamp=ts,
            payload=data.get("payload", {}),
        )


@dataclass(frozen=True)
class ProviderCapabilities:
    """Detailed capability record for an agent provider."""
    provider: str
    display_name: str
    available: bool
    detected_version: Optional[str]
    executable_path: Optional[str]
    supported_operations: List[str]
    supported_execution_modes: List[str]
    supported_skill_formats: List[str]
    detection_timestamp: datetime
    health_status: str  # 'healthy', 'degraded', 'unavailable'
    required_configuration: Dict[str, Any] = field(default_factory=dict)
    detection_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "display_name": self.display_name,
            "available": self.available,
            "detected_version": self.detected_version,
            "executable_path": self.executable_path,
            "supported_operations": self.supported_operations,
            "supported_execution_modes": self.supported_execution_modes,
            "supported_skill_formats": self.supported_skill_formats,
            "detection_timestamp": self.detection_timestamp.isoformat(),
            "health_status": self.health_status,
            "required_configuration": self.required_configuration,
            "detection_errors": self.detection_errors,
        }
