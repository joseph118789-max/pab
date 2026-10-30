"""Pytest fixtures for PersonaOS Agent Bridge (PAB)."""

import os
from pathlib import Path
import pytest
from pab.core.config import ConfigManager
from pab.core.models.agent import (
    AgentCapabilities,
    AgentIdentity,
    AgentInstructions,
    AgentPermissions,
    AgentPreferences,
    CanonicalAgentDefinition,
)
from pab.registry.agent_registry import AgentRegistry
from pab.skills.manager import SkillManager


@pytest.fixture
def temp_pab_dir(tmp_path: Path) -> Path:
    pab_dir = tmp_path / ".pab"
    pab_dir.mkdir(parents=True, exist_ok=True)
    return pab_dir


@pytest.fixture
def config_mgr(temp_pab_dir: Path) -> ConfigManager:
    return ConfigManager(root_dir=temp_pab_dir)


@pytest.fixture
def sample_agent_def() -> CanonicalAgentDefinition:
    return CanonicalAgentDefinition(
        id="devops-engineer",
        name="DevOps Engineer",
        description="Enterprise infrastructure and cloud orchestration specialist",
        version="1.0.0",
        identity=AgentIdentity(
            role="DevOps Engineer",
            persona="Senior Infrastructure Engineer",
            objective="Maintain reliable automated infrastructure",
            avatar_emoji="🛠️",
            style="technical and concise",
        ),
        instructions=AgentInstructions(
            system_prompt="Manage Kubernetes clusters and CI/CD pipelines safely."
        ),
        capabilities=AgentCapabilities(
            skills=["kubernetes", "linux-administration", "ansible"],
            tools={"allowed": ["read", "search", "terminal", "file_edit"], "denied": ["unrestricted-prod"]},
        ),
        preferences=AgentPreferences(
            model="inherit",
            reasoning_effort="high",
            response_style="technical",
        ),
        permissions=AgentPermissions(
            filesystem="workspace",
            shell_execution="approval_required",
            network="restricted",
        ),
    )
