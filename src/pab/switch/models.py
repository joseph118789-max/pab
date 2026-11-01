"""Data models for One-Command Agent Switching & Session Handoff."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SwitchMode(str, Enum):
    HANDOFF = "handoff"
    CLONE = "clone"
    SKILLS_ONLY = "skills-only"


class HandoffManifest(BaseModel):
    version: str = "2.0"
    handoff_id: str
    source_provider: str
    destination_provider: str
    source_agent_id: Optional[str] = None
    source_session_id: Optional[str] = None
    project_path: str
    export_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    imported_skills: List[str] = Field(default_factory=list)
    instruction_versions: Dict[str, str] = Field(default_factory=dict)
    memory_references: List[str] = Field(default_factory=list)
    file_hashes: Dict[str, str] = Field(default_factory=dict)
    migration_warnings: List[str] = Field(default_factory=list)

    # Canonical v2 structured fields
    source: Dict[str, Any] = Field(default_factory=dict)
    destination: Dict[str, Any] = Field(default_factory=dict)
    workspace: Dict[str, Any] = Field(default_factory=dict)
    worker_identity: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class SwitchPlan(BaseModel):
    source_provider: str
    destination_provider: str
    project_path: str
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    mode: SwitchMode = SwitchMode.HANDOFF
    skills_to_sync: List[str] = Field(default_factory=list)
    conflicting_skills: List[Dict[str, Any]] = Field(default_factory=list)
    instructions_to_transfer: List[str] = Field(default_factory=list)
    memories_to_transfer: List[str] = Field(default_factory=list)
    handoff_bundle_path: Optional[str] = None
    handoff_instruction: Optional[str] = None
    target_launch_cmd: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SwitchResult(BaseModel):
    success: bool
    handoff_id: str
    manifest: HandoffManifest
    launched: bool = False
    launch_cmd: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    handoff_dir: str
