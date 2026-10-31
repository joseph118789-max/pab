"""Unit and integration tests for Section 20 One-Command Agent Switching & Session Handoff."""

import json
from pathlib import Path
from unittest.mock import patch
import pytest
from typer.testing import CliRunner

from pab.cli.main import app
from pab.core.config import ConfigManager
from pab.core.models.agent import (
    AgentCapabilities,
    AgentIdentity,
    AgentInstructions,
    AgentPermissions,
    AgentPreferences,
    CanonicalAgentDefinition,
)
from pab.core.models.session import NormalizedSession, SessionContext
from pab.registry.agent_registry import AgentRegistry
from pab.skills.manager import SkillManager
from pab.core.models.skill import (
    CanonicalSkill,
    SkillManifest,
    SkillMetadata,
)
from pab.switch.engine import SwitchEngine
from pab.switch.models import SwitchMode


@pytest.fixture
def test_engine(config_mgr: ConfigManager, tmp_path: Path) -> SwitchEngine:
    engine = SwitchEngine(config_mgr)
    return engine


def test_plan_switch_clean_fallback(test_engine: SwitchEngine, tmp_path: Path):
    """Test switching with no prior session falls back cleanly."""
    plan = test_engine.plan_switch(
        source_provider_name="claude",
        target_provider_name="codex",
        project_path=str(tmp_path),
        mode=SwitchMode.HANDOFF,
    )
    assert plan.source_provider == "claude"
    assert plan.destination_provider == "codex"
    assert plan.project_path == str(tmp_path)
    assert plan.session_id is None
    assert any("No active session matched" in w for w in plan.warnings)


def test_plan_switch_modes_and_options(test_engine: SwitchEngine, tmp_path: Path):
    """Test switching modes (handoff, clone, skills-only) and options."""
    # Skills-only mode ignores memory
    plan = test_engine.plan_switch(
        source_provider_name="openclaw",
        target_provider_name="agy",
        project_path=str(tmp_path),
        mode=SwitchMode.SKILLS_ONLY,
    )
    assert plan.mode == SwitchMode.SKILLS_ONLY
    assert len(plan.memories_to_transfer) == 0

    # No-skills option
    plan_no_skills = test_engine.plan_switch(
        source_provider_name="codex",
        target_provider_name="claude",
        project_path=str(tmp_path),
        no_skills=True,
    )
    assert len(plan_no_skills.skills_to_sync) == 0


def test_plan_switch_conflicting_skills(test_engine: SwitchEngine):
    """Test conflicting skill version detection between source and destination."""
    # Register a canonical skill in SkillManager
    skill_dir = test_engine.config.skills_dir / "demo-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Demo skill\nmetadata:\n  version: 2.0.0\n---\n# Demo Skill v2\n",
        encoding="utf-8",
    )

    # Mock source provider agent with this skill
    source_prov = test_engine.providers.get("codex")
    target_prov = test_engine.providers.get("claude")

    with patch.object(source_prov, "get_agent", return_value={"id": "worker", "skills": ["demo-skill"]}):
        # Target already has demo-skill at v1.0.0
        with patch.object(target_prov, "list_skills", return_value=[{"name": "demo-skill", "version": "1.0.0"}]):
            warnings = []
            skills_to_sync, conflicts = test_engine._plan_skills(
                source_prov, target_prov, "worker", warnings
            )
            assert len(conflicts) == 1
            assert conflicts[0]["name"] == "demo-skill"
            assert conflicts[0]["source_version"] == "2.0.0"
            assert conflicts[0]["destination_version"] == "1.0.0"
            assert any("Skill version conflict" in w for w in warnings)
            assert "demo-skill" not in skills_to_sync


def test_execute_switch_creates_handoff_package(test_engine: SwitchEngine, tmp_path: Path):
    """Test executing a switch creates complete portable handoff bundle and logs to database."""
    # Mock source provider session export
    source_prov = test_engine.providers.get("claude")
    ctx = SessionContext(
        task_summary="Refactored database layer",
        original_objective="Upgrade database and run tests",
        completed_work=["Created connection pool", "Migrated models"],
        pending_work=["Add index on email", "Write load tests"],
        technical_decisions=["Use connection pooling for performance"],
        unresolved_issues=["High latency on batch inserts"],
    )
    mock_session = NormalizedSession(
        id="claude-sess-999",
        source_provider="claude",
        source_session_id="999",
        project=tmp_path.name,
        context=ctx,
    )

    with patch.object(source_prov, "export_session", return_value=mock_session):
        plan = test_engine.plan_switch(
            source_provider_name="claude",
            target_provider_name="codex",
            project_path=str(tmp_path),
            session_id="claude-sess-999",
            mode=SwitchMode.HANDOFF,
        )

        # Mock native launch so it does not actually spawn subprocess
        with patch("pab.switch.engine.execute_native_launch", return_value=0):
            res = test_engine.execute_switch(plan, dry_run=False)

        assert res.success is True
        assert res.launched is True
        handoff_dir = Path(res.handoff_dir)
        assert handoff_dir.is_dir()

        # Verify handoff bundle structure
        assert (handoff_dir / "HANDOFF.md").is_file()
        assert (handoff_dir / "manifest.json").is_file()
        assert (handoff_dir / "session.json").is_file()
        assert (handoff_dir / "context" / "task-summary.md").is_file()
        assert (handoff_dir / "context" / "decisions.md").is_file()
        assert (handoff_dir / "context" / "pending-work.md").is_file()
        assert (handoff_dir / "context" / "project-context.md").is_file()

        # Check content of HANDOFF.md
        handoff_text = (handoff_dir / "HANDOFF.md").read_text(encoding="utf-8")
        assert "Refactored database layer" in handoff_text
        assert "Upgrade database and run tests" in handoff_text
        assert "Created connection pool" in handoff_text
        assert "Add index on email" in handoff_text
        assert "Use connection pooling for performance" in handoff_text

        # Verify manifest file hashes
        manifest_data = json.loads((handoff_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest_data["handoff_id"] == res.handoff_id
        assert manifest_data["source_provider"] == "claude"
        assert manifest_data["destination_provider"] == "codex"
        assert "HANDOFF.md" in manifest_data["file_hashes"]
        assert "session.json" in manifest_data["file_hashes"]

        # Check switch recorded in DB
        record = test_engine.db.get_switch_by_handoff(res.handoff_id)
        assert record is not None
        assert record["target_provider"] == "codex"
        assert record["source_provider"] == "claude"

        # Test switch inspect
        history = test_engine.db.get_switch_history()
        assert len(history) >= 1
        assert any(h["handoff_id"] == res.handoff_id for h in history)

        # Test rollback
        rolled_back = test_engine.rollback_switch(res.handoff_id)
        assert rolled_back is True
        assert not handoff_dir.exists()


def test_cli_switch_dry_run_and_passthrough():
    """Test CLI command execution with --dry-run and pass-through args."""
    runner = CliRunner()

    # pab codex --from claude --dry-run -- --flag-to-codex
    result = runner.invoke(app, ["codex", "--from", "claude", "--dry-run", "--", "--flag-to-codex"])
    assert result.exit_code == 0
    assert "Switching from claude ➔ codex" in result.output
    assert "codex --flag-to-codex" in result.output

    # pab agy --from codex --dry-run
    result_agy = runner.invoke(app, ["agy", "--from", "codex", "--dry-run"])
    assert result_agy.exit_code == 0
    assert "Switching from codex ➔ agy" in result_agy.output

    # pab claude --from openclaw --dry-run
    result_claude = runner.invoke(app, ["claude", "--from", "openclaw", "--dry-run"])
    assert result_claude.exit_code == 0
    assert "Switching from openclaw ➔ claude" in result_claude.output


def test_cli_switch_history_and_inspect():
    """Test CLI switch history and inspect commands."""
    runner = CliRunner()

    result_hist = runner.invoke(app, ["switch", "history"])
    assert result_hist.exit_code == 0
    assert "Agent Switching & Session Handoff History" in result_hist.output

    # Inspect non-existent handoff
    result_inspect = runner.invoke(app, ["switch", "inspect", "nonexistent-id"])
    assert result_inspect.exit_code == 1
    assert "not found" in result_inspect.output
