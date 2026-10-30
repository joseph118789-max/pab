"""Canonical Agent Schema and validation models."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class AgentIdentity(BaseModel):
    role: str = Field(..., description="Primary role or title of the agent")
    persona: str = Field("", description="Persona background or archetype")
    objective: str = Field("", description="Core mission or objective")
    avatar_emoji: str = Field("🤖", description="Avatar emoji or visual representation")
    style: str = Field("professional", description="Communication tone and style")


class AgentInstructions(BaseModel):
    system_prompt: Optional[str] = Field(None, description="Path to system prompt or AGENTS.md")
    developer_prompt: Optional[str] = Field(None, description="Path to developer instructions")
    user_prompt: Optional[str] = Field(None, description="Path to user guidelines / USER.md")
    soul_prompt: Optional[str] = Field(None, description="Path to personality guidelines / SOUL.md")
    custom: Dict[str, str] = Field(default_factory=dict, description="Custom named instruction files")


class AgentToolCapabilities(BaseModel):
    allowed: List[str] = Field(default_factory=lambda: ["read", "search", "terminal", "file_edit"])
    denied: List[str] = Field(default_factory=list)


class AgentCapabilities(BaseModel):
    skills: List[str] = Field(default_factory=list, description="Skill identifiers")
    tools: AgentToolCapabilities = Field(default_factory=AgentToolCapabilities)


class AgentPreferences(BaseModel):
    model: str = Field("inherit", description="Model name or 'inherit'")
    reasoning_effort: str = Field("inherit", description="Reasoning effort: low|medium|high|inherit")
    response_style: str = Field("technical", description="Response style: technical|concise|detailed")


class AgentPermissions(BaseModel):
    filesystem: Literal["workspace", "restricted", "unrestricted"] = "workspace"
    shell_execution: Literal["auto", "approval_required", "denied"] = "approval_required"
    network: Literal["denied", "restricted", "unrestricted"] = "restricted"


class AgentMemoryConfig(BaseModel):
    enabled: bool = True
    scope: List[str] = Field(default_factory=lambda: ["global", "project", "agent"])


class ProviderConfig(BaseModel):
    enabled: bool = True
    workspace: Optional[str] = None
    model: Optional[str] = None
    tools_profile: Optional[str] = None
    extensions: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific native settings")


class CanonicalAgentDefinition(BaseModel):
    id: str = Field(..., description="Unique alphanumeric identifier (e.g. devops-engineer)")
    name: str = Field(..., description="Human-readable name")
    description: str = Field("", description="Detailed description of agent purpose")
    version: str = Field("1.0.0", description="Semantic version string")
    identity: AgentIdentity = Field(default_factory=lambda: AgentIdentity(role="General Assistant"))
    instructions: AgentInstructions = Field(default_factory=AgentInstructions)
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    preferences: AgentPreferences = Field(default_factory=AgentPreferences)
    permissions: AgentPermissions = Field(default_factory=AgentPermissions)
    memory: AgentMemoryConfig = Field(default_factory=AgentMemoryConfig)
    providers: Dict[str, ProviderConfig] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CanonicalAgentProfile(BaseModel):
    schema_version: str = "1.0"
    agent: CanonicalAgentDefinition
