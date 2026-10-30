"""Open Agent Skills canonical models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SkillMetadata(BaseModel):
    short_description: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = "1.0.0"
    tags: List[str] = Field(default_factory=list)
    custom: Dict[str, Any] = Field(default_factory=dict)


class SkillManifest(BaseModel):
    name: str = Field(..., description="Unique skill name in kebab-case")
    description: str = Field(..., description="Clear description of when and how the skill is used")
    metadata: SkillMetadata = Field(default_factory=SkillMetadata)
    dependencies: List[str] = Field(default_factory=list)
    license: Optional[str] = None


class SkillResource(BaseModel):
    relative_path: str
    content_hash: str
    size_bytes: int
    is_executable: bool = False


class CanonicalSkill(BaseModel):
    manifest: SkillManifest
    body: str = Field(..., description="Markdown body explaining workflow, steps, guidance")
    scripts: List[SkillResource] = Field(default_factory=list)
    references: List[SkillResource] = Field(default_factory=list)
    assets: List[SkillResource] = Field(default_factory=list)
    source_path: Optional[str] = None
