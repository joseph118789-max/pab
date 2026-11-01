"""Unit tests for Agent Registry and Provider Deployment."""

from pathlib import Path
import tomlkit
import yaml
from pab.core.config import ConfigManager
from pab.core.models.agent import CanonicalAgentDefinition
from pab.registry.agent_registry import AgentRegistry


def test_agent_lifecycle(config_mgr: ConfigManager, sample_agent_def: CanonicalAgentDefinition):
    registry = AgentRegistry(config_mgr)

    # 1. Create
    profile = registry.create_agent(sample_agent_def)
    assert profile.agent.id == "devops-engineer"
    assert profile.agent.name == "DevOps Engineer"

    # 2. Get
    loaded = registry.get_agent("devops-engineer")
    assert loaded is not None
    assert loaded.agent.identity.role == "DevOps Engineer"

    # 3. Clone
    cloned = registry.clone_agent("devops-engineer", "sre-engineer", "SRE Engineer")
    assert cloned.agent.id == "sre-engineer"
    assert cloned.agent.name == "SRE Engineer"
    assert registry.get_agent("sre-engineer") is not None

    # 4. Update and diff
    updated_def = sample_agent_def.model_copy(deep=True)
    updated_def.version = "1.1.0"
    updated_def.description = "Updated DevOps role"
    diff = registry.diff_agent("devops-engineer", updated_def)
    assert "1.1.0" in diff

    updated_profile = registry.update_agent(updated_def, commit_message="Bumped to 1.1.0")
    assert updated_profile.agent.version == "1.1.0"

    # 5. Rollback
    rolled_back = registry.rollback_agent("devops-engineer", "1.0.0")
    assert rolled_back.agent.version == "1.0.0"

    # 6. Delete
    assert registry.delete_agent("sre-engineer") is True
    assert registry.get_agent("sre-engineer") is None


def test_agent_deploy_all_providers(
    tmp_path: Path,
    config_mgr: ConfigManager,
    sample_agent_def: CanonicalAgentDefinition,
):
    # Setup mock provider dirs
    oc_home = tmp_path / "mock_openclaw"
    gemini_home = tmp_path / "mock_gemini"
    codex_home = tmp_path / "mock_codex"
    claude_home = tmp_path / "mock_claude"

    from pab.providers.openclaw.agents import compile_openclaw_agent
    from pab.providers.agy.agents import compile_agy_agent
    from pab.providers.codex.agents import compile_codex_agent
    from pab.providers.claude.agents import compile_claude_agent
    from pab.providers.dsh.agents import compile_dsh_agent
    from pab.providers.pi.agents import compile_pi_agent

    # 1. Deploy OpenClaw
    oc_res = compile_openclaw_agent(sample_agent_def, home_dir=oc_home)
    assert oc_res["status"] == "deployed"
    ws = Path(oc_res["workspace"])
    assert (ws / "IDENTITY.md").is_file()
    assert (ws / "SOUL.md").is_file()
    assert (ws / "USER.md").is_file()
    assert (ws / "AGENTS.md").is_file()
    assert (oc_home / "openclaw.json").is_file()

    # 2. Deploy Antigravity (agy)
    agy_res = compile_agy_agent(sample_agent_def, config_dir=gemini_home / "config")
    assert agy_res["status"] == "deployed"
    agy_file = Path(agy_res["path"])
    assert agy_file.is_file()
    content = agy_file.read_text("utf-8")
    assert "name: devops-engineer" in content
    assert "model: inherit" in content

    # 3. Deploy Codex
    codex_res = compile_codex_agent(sample_agent_def, home_dir=codex_home)
    assert codex_res["status"] == "deployed"
    codex_file = Path(codex_res["path"])
    assert codex_file.is_file()
    toml_data = tomlkit.parse(codex_file.read_text("utf-8"))
    assert toml_data["name"] == sample_agent_def.name
    assert "kubernetes" in toml_data.get("developer_instructions", "") or "kubernetes" in str(toml_data)

    # 4. Deploy Claude Code
    claude_res = compile_claude_agent(sample_agent_def, home_dir=claude_home)
    assert claude_res["status"] == "deployed"
    claude_file = Path(claude_res["path"])
    assert claude_file.is_file()
    claude_content = claude_file.read_text("utf-8")
    assert "name: devops-engineer" in claude_content
    assert "tools:" in claude_content

    # 5. Deploy DSH
    dsh_home = tmp_path / "mock_dsh"
    dsh_res = compile_dsh_agent(sample_agent_def, home_dir=dsh_home)
    dsh_dir = Path(dsh_res["path"])
    assert dsh_dir.is_dir()
    assert (dsh_dir / "cordis.patch.yml").is_file()
    assert (dsh_dir / "package.json").is_file()

    # 6. Deploy Pi
    pi_home = tmp_path / "mock_pi"
    pi_res = compile_pi_agent(sample_agent_def, home_dir=pi_home)
    pi_file = Path(pi_res["path"])
    assert pi_file.is_file()
    assert "devops-engineer" in pi_file.read_text("utf-8")


def test_import_openclaw_native_agent(tmp_path: Path, config_mgr: ConfigManager):
    from pab.providers.openclaw.agents import import_openclaw_agent
    # Setup mock openclaw home
    oc_home = tmp_path / "openclaw_root"
    ws = oc_home / "workspace"
    ws.mkdir(parents=True)
    (ws / "IDENTITY.md").write_text("# IDENTITY.md\n- **Name:** Lobster Master\n- **Emoji:** 🦞\n- **Creature:** Crustacean\n", encoding="utf-8")
    (ws / "SOUL.md").write_text("# SOUL.md\nBe resourceful and helpful.\n", encoding="utf-8")
    (ws / "AGENTS.md").write_text("# AGENTS.md\nWorkspace guidelines.\n", encoding="utf-8")
    (ws / "skills").mkdir()
    (ws / "skills" / "docker-test").mkdir()
    (ws / "skills" / "docker-test" / "SKILL.md").write_text("---\nname: docker-test\ndescription: Docker skill test\n---\n", encoding="utf-8")

    import json
    cfg = {"agents": {"entries": {"main": {"model": "test-model", "workspace": str(ws)}}}}
    (oc_home / "openclaw.json").write_text(json.dumps(cfg), encoding="utf-8")

    agent_def = import_openclaw_agent("main", home_dir=oc_home)
    assert agent_def is not None
    assert agent_def.id == "main"
    assert agent_def.name == "Lobster Master"
    assert agent_def.identity.avatar_emoji == "🦞"
    assert "docker-test" in agent_def.capabilities.skills
    assert agent_def.preferences.model == "test-model"
