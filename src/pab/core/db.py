"""SQLite storage layer for PAB registry and audit trail."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class Database:
    """Manages SQLite tables and transactions for PAB."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    schema_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    schema_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    commit_message TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS skills (
                    name TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    path TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    source_provider TEXT,
                    source_path TEXT,
                    project_id TEXT,
                    agent_id TEXT,
                    untrusted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    source_provider TEXT NOT NULL,
                    source_session_id TEXT NOT NULL,
                    project TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    exported_at TEXT NOT NULL,
                    data_json TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    provider TEXT,
                    details_json TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_plans (
                    plan_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    approved INTEGER NOT NULL DEFAULT 0,
                    applied INTEGER NOT NULL DEFAULT 0,
                    plan_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def record_audit(
        self,
        event_type: str,
        resource_type: str,
        resource_id: str,
        provider: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert an audit log entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_log (timestamp, event_type, resource_type, resource_id, provider, details_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    event_type,
                    resource_type,
                    resource_id,
                    provider,
                    json.dumps(details or {}),
                ),
            )
            conn.commit()

    def get_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
