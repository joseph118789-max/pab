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
