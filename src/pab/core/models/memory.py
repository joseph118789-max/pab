"""Unified Memory models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


MemoryScope = Literal["user", "global", "project", "agent", "daily", "imported", "handoff"]


class MemoryItem(BaseModel):
    id: str = Field(..., description="Unique memory identifier or SHA-256 hash")
    title: str = Field(..., description="Short summary title")
    content: str = Field(..., description="Markdown memory content")
    scope: MemoryScope = "global"
    source_provider: Optional[str] = None
    source_path: Optional[str] = None
    project_id: Optional[str] = None
    agent_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content_hash: str = Field("", description="SHA-256 of normalized content")
    tags: List[str] = Field(default_factory=list)
    untrusted: bool = Field(False, description="Whether memory is imported and unverified")
    metadata: Dict[str, Any] = Field(default_factory=dict)
