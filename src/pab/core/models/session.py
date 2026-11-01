"""Normalized Session and Portable Handoff models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SessionContext(BaseModel):
    task_summary: str = Field("", description="High level summary of current progress")
    original_objective: str = Field("", description="Original user prompt or prompt goal")
    completed_work: List[str] = Field(default_factory=list)
    pending_work: List[str] = Field(default_factory=list)
    technical_decisions: List[str] = Field(default_factory=list)
    important_files: List[str] = Field(default_factory=list)
    commands_executed: List[str] = Field(default_factory=list)
    unresolved_issues: List[str] = Field(default_factory=list)
    git_branch: Optional[str] = None
    git_diff_summary: Optional[str] = None


class NormalizedSession(BaseModel):
    id: str = Field(..., description="Unique normalized session ID")
    source_provider: str = Field(..., description="Source provider: openclaw|agy|codex|claude")
    source_session_id: str = Field(..., description="Original provider session ID")
    project: str = Field("default", description="Project identifier")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    exported_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    context: SessionContext = Field(default_factory=SessionContext)
    transcript_file: Optional[str] = None
    raw_transcript: Optional[str] = None
    artifacts: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HandoffBundle(BaseModel):
    bundle_id: str
    source_provider: str
    target_provider: Optional[str] = None
    session_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    handoff_markdown: str
    context: SessionContext
    workspace_diff: Optional[str] = None
    transcript_excerpt: Optional[str] = None
    skills_referenced: List[str] = Field(default_factory=list)
    memory_references: List[str] = Field(default_factory=list)
