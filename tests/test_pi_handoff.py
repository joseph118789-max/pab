"""Tests for Canonical Session Handoff v2 and Claude/Codex -> Pi context migrations."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pab.core.config import ConfigManager
from pab.core.models.session import NormalizedSession, SessionContext
from pab.providers.pi.sessions import export_pi_session, list_pi_sessions
from pab.switch.engine import SwitchEngine
from pab.switch.models import SwitchMode


def test_pi_session_exporter(tmp_path: Path):
    """Test reading and normalizing Pi session tree JSONL files."""
    sess_dir = tmp_path / "sessions" / "--test-project--"
    sess_dir.mkdir(parents=True, exist_ok=True)
    sess_file = sess_dir / "2026-11-01_sess-test-999.jsonl"

    lines = [
        json.dumps({"type": "session", "version": 3, "id": "sess-test-999", "cwd": str(tmp_path)}),
        json.dumps({
            "type": "message",
            "id": "m1",
            "parentId": None,
            "message": {"role": "user", "content": "Implement memory search and deduping"},
        }),
        json.dumps({
            "type": "message",
            "id": "m2",
            "parentId": "m1",
            "message": {
                "role": "assistant",
                "content": "Completed:\n- [x] Created memory index\n- [x] Implemented sha256 dedup\nDecision: used sqlite fts5 for search.",
            },
        }),
        json.dumps({
            "type": "message",
            "id": "m3",
            "parentId": "m2",
            "message": {
                "role": "toolResult",
                "toolName": "edit",
                "content": "Successfully updated memory/hub.py",
            },
        }),
    ]
    sess_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with patch("pab.providers.pi.sessions.get_pi_sessions_dir", return_value=tmp_path / "sessions"):
        sessions = list_pi_sessions()
        assert len(sessions) >= 1
        assert any("sess-test-999" in s["id"] for s in sessions)

        norm = export_pi_session("pi:sess-test-999")
        assert norm is not None
        assert norm.source_provider == "pi"
        assert norm.source_session_id == "sess-test-999"
        assert "Implement memory search" in norm.context.original_objective
        assert len(norm.context.completed_work) >= 1
        assert any("sqlite fts5" in d for d in norm.context.technical_decisions)


def test_claude_to_pi_handoff_v2(config_mgr: ConfigManager, tmp_path: Path):
    """AT-6 & AT-7: Test cross-agent handoff from Claude to Pi generates complete v2 bundle."""
    engine = SwitchEngine(config_mgr)
    claude_prov = engine.providers.get("claude")

    ctx = SessionContext(
        task_summary="Refactored database pooling for high concurrency",
        original_objective="Design and optimize database concurrency",
        completed_work=["Configured thread pools", "Added lock benchmarks"],
        pending_work=["Independent security review"],
        technical_decisions=["Decided to avoid global locks in favour of row leases"],
        important_files=["src/pab/core/db.py"],
    )
    mock_session = NormalizedSession(
        id="claude-sess-777",
        source_provider="claude",
        source_session_id="claude-777",
        project=tmp_path.name,
        context=ctx,
        raw_transcript=json.dumps([{"role": "user", "content": "Optimize db"}, {"role": "assistant", "content": "Done"}]),
    )

    with patch.object(claude_prov, "export_session", return_value=mock_session):
        plan = engine.plan_switch(
            source_provider_name="claude",
            target_provider_name="pi",
            project_path=str(tmp_path),
            session_id="claude-777",
            mode=SwitchMode.HANDOFF,
        )

        with patch("pab.switch.engine.execute_native_launch", return_value=0):
            res = engine.execute_switch(plan, dry_run=False)

        assert res.success is True
        handoff_dir = Path(res.handoff_dir)
        assert handoff_dir.is_dir()

        # Check Canonical v2 files
        assert (handoff_dir / "manifest.json").is_file()
        assert (handoff_dir / "summary.md").is_file()
        assert (handoff_dir / "context.json").is_file()
        assert (handoff_dir / "source.json").is_file()
        assert (handoff_dir / "transcript.jsonl").is_file()

        # Verify manifest v2 schema
        manifest_data = json.loads((handoff_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest_data.get("version") == "2.0"

        # Session ID Integrity: source and destination session IDs are separate
        assert manifest_data["source"]["provider"] == "claude"
        assert manifest_data["source"]["session_id"] == "claude-777"
        assert manifest_data["destination"]["provider"] == "pi"
        assert manifest_data["destination"]["session_id"] != "claude-777"
        assert "pi:new" in manifest_data["destination"]["session_id"]

        # Worker identity & context preserved
        assert manifest_data["context"]["original_objective"] == "Design and optimize database concurrency"
        assert "Refactored database pooling" in manifest_data["context"]["task_summary"]
        assert manifest_data["provenance"]["generator"] == "PAB Handoff Engine v2.0"

        # Check that canonical .pab/sessions/handoffs/ was mirrored
        canonical_dir = tmp_path / ".pab" / "sessions" / "handoffs" / res.handoff_id
        assert canonical_dir.is_dir()
        assert (canonical_dir / "manifest.json").is_file()
