"""Sync Engine change plan models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


ActionType = Literal["create", "update", "delete", "noop", "conflict"]


class PlannedOperation(BaseModel):
    resource_type: Literal["agent", "skill", "memory", "instruction"]
    resource_id: str
    target_provider: str
    action: ActionType
    target_path: str
    description: str
    diff: Optional[str] = None
    backup_path: Optional[str] = None


class SyncPlan(BaseModel):
    plan_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "canonical"
    targets: List[str] = Field(default_factory=list)
    operations: List[PlannedOperation] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    approved: bool = False
    applied: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
