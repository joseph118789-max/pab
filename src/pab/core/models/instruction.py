"""Instruction and AGENTS.md models."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


InstructionScope = Literal["global", "project", "agent", "provider_extension"]


class InstructionRule(BaseModel):
    id: str
    title: str
    content: str
    category: str = "general"
    precedence: int = 100
    scope: InstructionScope = "project"
    source_file: Optional[str] = None


class CanonicalInstructions(BaseModel):
    version: str = "1.0.0"
    agents_md: str = Field(..., description="Canonical AGENTS.md markdown content")
    developer_md: Optional[str] = None
    user_md: Optional[str] = None
    soul_md: Optional[str] = None
    rules: List[InstructionRule] = Field(default_factory=list)
    provider_overrides: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
