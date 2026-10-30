"""Unit tests for PersonaOS Bridge."""

from pathlib import Path
from pab.core.config import ConfigManager
from pab.personaos.bridge import PersonaOSBridge
from pab.personaos.profile_converter import (
    convert_personaos_profile_to_canonical,
    load_personaos_profile,
)


def test_personaos_profile_conversion(tmp_path: Path):
    profile_dir = tmp_path / "worker-devops-001"
    profile_dir.mkdir()
    v1_file = profile_dir / "v1.yaml"
    v1_file.write_text(
        """
version: 1
role: devops
description: Infrastructure and deployment specialist
persona:
  style: cautious
  communication: concise
  autonomy: medium
  goals:
    - reliable deployments
    - minimize production risk
model: claude-sonnet
instructions: |
  You are a DevOps engineer. Manage infrastructure safely.
skills:
  - kubernetes
  - linux
  - ansible
permissions:
  - staging.deploy
  - production.read
runtime: openclaw
""",
        encoding="utf-8",
    )

    agent_def = load_personaos_profile(v1_file)
    assert agent_def.id == "worker-devops-001"
    assert agent_def.name == "PersonaOS Devops"
    assert agent_def.identity.role == "Devops"
    assert "reliable deployments" in agent_def.identity.objective
    assert agent_def.capabilities.skills == ["kubernetes", "linux", "ansible"]
    assert agent_def.preferences.model == "claude-sonnet"
    assert agent_def.permissions.shell_execution == "approval_required"


def test_personaos_bridge_sync_and_readiness(tmp_path: Path, config_mgr: ConfigManager):
    profiles_root = tmp_path / "profiles"
    worker_dir = profiles_root / "worker-qa-001"
    worker_dir.mkdir(parents=True)
    v1_file = worker_dir / "v1.yaml"
    v1_file.write_text(
        """
version: 1
role: qa
description: Quality assurance and test automation engineer
skills:
  - pytest
  - playwright
model: inherit
instructions: Execute comprehensive test suites.
""",
        encoding="utf-8",
    )

    bridge = PersonaOSBridge(config_mgr)
    sync_res = bridge.sync_worker_profiles(profiles_root, target_providers=["agy", "codex"])
    assert "worker-qa-001" in sync_res["imported"]

    # Verify agent is in PAB registry
    profile = bridge.registry.get_agent("worker-qa-001")
    assert profile is not None
    assert profile.agent.name == "PersonaOS Qa"

    # Verify skills were auto-provisioned
    assert bridge.skills.get_skill("pytest") is not None
    assert bridge.skills.get_skill("playwright") is not None

    # Verify readiness report
    readiness = bridge.get_readiness_report()
    assert readiness["registered_agents"] >= 1
    assert "worker-qa-001" in readiness["agents"]
