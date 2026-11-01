"""PAB Universal Agent Orchestration Data Models.

Defines canonical contracts for Runs, Tasks, Dispatches, Decision Gates, and Inter-Agent Messages,
mirroring Orca orchestration semantics while preserving PersonaOS task authority.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Dict, List, Optional


class RunStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class DispatchStatus(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    SETTLED = "settled"
    COMPLETED = "completed"
    FAILED = "failed"


class GateStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    EXPIRED = "expired"


@dataclass(frozen=True)
class OrchestrationRun:
    """Overarching workflow run boundary and inbox namespace."""
    run_id: str
    name: str
    objective: str
    workspace_path: str
    status: RunStatus = RunStatus.ACTIVE
    coordinator_agent: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "name": self.name,
            "objective": self.objective,
            "workspace_path": self.workspace_path,
            "status": self.status.value,
            "coordinator_agent": self.coordinator_agent,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OrchestrationRun:
        raw_status = data.get("status", RunStatus.ACTIVE.value)
        status = RunStatus(raw_status) if raw_status in [s.value for s in RunStatus] else RunStatus.ACTIVE
        created = datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"]
        return cls(
            run_id=data["run_id"],
            name=data["name"],
            objective=data["objective"],
            workspace_path=data["workspace_path"],
            status=status,
            coordinator_agent=data.get("coordinator_agent"),
            created_at=created,
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class OrchestrationTask:
    """Unit of work within an OrchestrationRun linked to PersonaOS task."""
    task_id: str
    run_id: str
    title: str
    spec: str
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_worker_id: Optional[str] = None
    gate_id: Optional[str] = None
    personaos_task_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "title": self.title,
            "spec": self.spec,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "assigned_worker_id": self.assigned_worker_id,
            "gate_id": self.gate_id,
            "personaos_task_id": self.personaos_task_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OrchestrationTask:
        raw_status = data.get("status", TaskStatus.PENDING.value)
        status = TaskStatus(raw_status) if raw_status in [s.value for s in TaskStatus] else TaskStatus.PENDING
        created = datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"]
        return cls(
            task_id=data["task_id"],
            run_id=data["run_id"],
            title=data["title"],
            spec=data["spec"],
            dependencies=data.get("dependencies", []),
            status=status,
            assigned_worker_id=data.get("assigned_worker_id"),
            gate_id=data.get("gate_id"),
            personaos_task_id=data.get("personaos_task_id"),
            created_at=created,
        )


@dataclass(frozen=True)
class OrchestrationDispatch:
    """Execution attempt of an OrchestrationTask assigned to an agent runtime."""
    dispatch_id: str
    task_id: str
    run_id: str
    agent_provider: str
    worker_id: str
    worktree_path: str
    status: DispatchStatus = DispatchStatus.STARTING
    terminal_handle: Optional[str] = None
    process_id: Optional[int] = None
    attempt_number: int = 1
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    result_summary: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dispatch_id": self.dispatch_id,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "agent_provider": self.agent_provider,
            "worker_id": self.worker_id,
            "worktree_path": self.worktree_path,
            "status": self.status.value,
            "terminal_handle": self.terminal_handle,
            "process_id": self.process_id,
            "attempt_number": self.attempt_number,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result_summary": self.result_summary,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OrchestrationDispatch:
        raw_status = data.get("status", DispatchStatus.STARTING.value)
        status = DispatchStatus(raw_status) if raw_status in [s.value for s in DispatchStatus] else DispatchStatus.STARTING
        started = datetime.fromisoformat(data["started_at"]) if isinstance(data["started_at"], str) else data["started_at"]
        completed = None
        if data.get("completed_at"):
            completed = datetime.fromisoformat(data["completed_at"]) if isinstance(data["completed_at"], str) else data["completed_at"]
        return cls(
            dispatch_id=data["dispatch_id"],
            task_id=data["task_id"],
            run_id=data["run_id"],
            agent_provider=data["agent_provider"],
            worker_id=data["worker_id"],
            worktree_path=data["worktree_path"],
            status=status,
            terminal_handle=data.get("terminal_handle"),
            process_id=data.get("process_id"),
            attempt_number=int(data.get("attempt_number", 1)),
            started_at=started,
            completed_at=completed,
            result_summary=data.get("result_summary"),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class DecisionGate:
    """Approval checkpoint blocking task progression until resolved."""
    gate_id: str
    task_id: str
    question: str
    options: List[str] = field(default_factory=lambda: ["approve", "reject"])
    status: GateStatus = GateStatus.PENDING
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "task_id": self.task_id,
            "question": self.question,
            "options": self.options,
            "status": self.status.value,
            "resolution": self.resolution,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DecisionGate:
        raw_status = data.get("status", GateStatus.PENDING.value)
        status = GateStatus(raw_status) if raw_status in [s.value for s in GateStatus] else GateStatus.PENDING
        resolved = None
        if data.get("resolved_at"):
            resolved = datetime.fromisoformat(data["resolved_at"]) if isinstance(data["resolved_at"], str) else data["resolved_at"]
        return cls(
            gate_id=data["gate_id"],
            task_id=data["task_id"],
            question=data["question"],
            options=data.get("options", ["approve", "reject"]),
            status=status,
            resolution=data.get("resolution"),
            resolved_by=data.get("resolved_by"),
            resolved_at=resolved,
        )


@dataclass(frozen=True)
class OrchestrationMessage:
    """Threaded inter-agent and coordinator communication message."""
    message_id: str
    run_id: str
    subject: str
    msg_type: str = "status"
    from_handle: str = "coordinator"
    to_target: Optional[str] = None
    thread_id: Optional[str] = None
    body: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "from_handle": self.from_handle,
            "to_target": self.to_target,
            "msg_type": self.msg_type,
            "subject": self.subject,
            "body": self.body,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OrchestrationMessage:
        ts = datetime.fromisoformat(data["timestamp"]) if isinstance(data["timestamp"], str) else data["timestamp"]
        return cls(
            message_id=data["message_id"],
            run_id=data["run_id"],
            thread_id=data.get("thread_id"),
            from_handle=data.get("from_handle", "coordinator"),
            to_target=data.get("to_target"),
            msg_type=data.get("msg_type", "status"),
            subject=data["subject"],
            body=data.get("body"),
            payload=data.get("payload", {}),
            timestamp=ts,
        )
