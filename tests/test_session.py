"""Unit tests for Cross-Platform Session Migration and Portable Handoff."""

from pathlib import Path
import pytest
from pab.core.config import ConfigManager
from pab.core.exceptions import ProviderExecutionError
from pab.core.models.session import NormalizedSession, SessionContext
from pab.sessions.handoff import create_handoff_package, generate_handoff_markdown
from pab.sessions.manager import SessionMigrationManager


def test_session_handoff_bundle_generation(tmp_path: Path):
    ctx = SessionContext(
        task_summary="Migrated database schema to v2",
        original_objective="Upgrade database tables and configure indexes",
        completed_work=["Applied migration 001", "Verified foreign keys"],
        pending_work=["Create index on user_id"],
        technical_decisions=["Used BIGINT for high-traffic primary keys"],
        important_files=["src/models.py", "alembic/versions/001.py"],
        unresolved_issues=["Warning on slow query for report generation"],
    )

    session = NormalizedSession(
        id="session-test-001",
        source_provider="codex",
        source_session_id="codex-sess-123",
        project="test-proj",
        context=ctx,
    )

    bundle = create_handoff_package(session, "agy", tmp_path)
    assert bundle.bundle_id.startswith("handoff-codex")
    assert "Migrated database schema to v2" in bundle.handoff_markdown

    bundle_dir = tmp_path / bundle.bundle_id
    assert (bundle_dir / "HANDOFF.md").is_file()
    assert (bundle_dir / "context.json").is_file()


def test_cross_provider_native_resume_is_blocked(config_mgr: ConfigManager):
    sm = SessionMigrationManager(config_mgr)

    # Mock an exported session originating from codex
    ctx = SessionContext(task_summary="Working on feature X")
    norm = NormalizedSession(
        id="codex-session-abc",
        source_provider="codex",
        source_session_id="abc",
        context=ctx,
    )
    # Save into SQLite
    import json
    with sm.db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO sessions (id, source_provider, source_session_id, project, created_at, exported_at, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (norm.id, norm.source_provider, norm.source_session_id, norm.project, norm.created_at, norm.exported_at, json.dumps(norm.model_dump())),
        )
        conn.commit()

    # Attempting to resume a codex session on claude must raise ProviderExecutionError
    with pytest.raises(ProviderExecutionError) as exc_info:
        sm.resume_session("claude", "abc")

    assert "Direct native resume across different providers is unsupported" in str(exc_info.value)
    assert "pab session handoff" in str(exc_info.value)


def test_openclaw_session_alias_resolution_and_export(tmp_path: Path):
    import sqlite3
    import json
    from pab.providers.openclaw.sessions import export_openclaw_session

    fake_home = tmp_path / ".openclaw"
    agent_dir = fake_home / "agents" / "main"
    sess_dir = agent_dir / "sessions"
    db_dir = agent_dir / "agent"
    db_dir.mkdir(parents=True, exist_ok=True)
    sess_dir.mkdir(parents=True, exist_ok=True)

    db_path = db_dir / "openclaw-agent.sqlite"
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE session_windows (session_id TEXT PRIMARY KEY);
    """)
    c.execute("""
        CREATE TABLE conversations (
            conversation_id TEXT PRIMARY KEY,
            channel TEXT,
            peer_id TEXT,
            delivery_target TEXT,
            label TEXT
        );
    """)
    c.execute("""
        CREATE TABLE session_conversations (
            session_id TEXT,
            conversation_id TEXT,
            last_seen_at INTEGER,
            PRIMARY KEY (session_id, conversation_id)
        );
    """)
    c.execute("""
        CREATE TABLE transcript_events (
            session_id TEXT,
            seq INTEGER,
            event_json TEXT,
            PRIMARY KEY (session_id, seq)
        );
    """)

    test_sid = "test-session-uuid-1234"
    c.execute("INSERT INTO session_windows VALUES (?)", (test_sid,))
    c.execute("INSERT INTO conversations VALUES (?, ?, ?, ?, ?)", ("conv_1", "telegram", "-5036746892", "telegram:-5036746892", "telegram:g-projects-ansible-hardening"))
    c.execute("INSERT INTO session_conversations VALUES (?, ?, ?)", (test_sid, "conv_1", 1792459479000))
    
    ev1 = {"type": "message", "message": {"role": "user", "content": "Hardening check on DB2 RHEL playbook"}}
    ev2 = {"type": "message", "message": {"role": "assistant", "content": "Completed playbook audit with 0 errors"}}
    c.execute("INSERT INTO transcript_events VALUES (?, ?, ?)", (test_sid, 0, json.dumps(ev1)))
    c.execute("INSERT INTO transcript_events VALUES (?, ?, ?)", (test_sid, 1, json.dumps(ev2)))
    conn.commit()
    conn.close()

    # Export using telegram alias
    exported = export_openclaw_session("telegram:group:-5036746892", home_dir=fake_home)
    assert exported is not None
    assert exported.id == f"openclaw-main-{test_sid}"
    assert "Hardening check on DB2" in exported.context.original_objective
    assert "Completed playbook audit" in exported.context.task_summary
    assert exported.project == "ansible-hardening"

