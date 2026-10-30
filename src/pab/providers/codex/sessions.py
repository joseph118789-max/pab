"""OpenAI Codex session discovery and export."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.session import NormalizedSession, SessionContext
from pab.providers.codex.config import get_codex_home


def list_codex_sessions(home_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    home = home_dir or get_codex_home()
    sessions = []
    logs_db = home / "logs_2.sqlite"
    if not logs_db.is_file():
        return sessions

    try:
        conn = sqlite3.connect(str(logs_db))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        if "sessions" in tables:
            cursor.execute("SELECT id, created_at FROM sessions ORDER BY created_at DESC LIMIT 50")
            for row in cursor.fetchall():
                sessions.append({
                    "id": str(row[0]),
                    "created_at": str(row[1]),
                    "source": "sqlite",
                })
        elif "logs" in tables:
            cursor.execute("SELECT DISTINCT session_id FROM logs WHERE session_id IS NOT NULL LIMIT 50")
            for row in cursor.fetchall():
                sessions.append({
                    "id": str(row[0]),
                    "source": "sqlite",
                })
        conn.close()
    except Exception:
        pass
    return sessions


def export_codex_session(
    session_id: str,
    home_dir: Optional[Path] = None,
) -> Optional[NormalizedSession]:
    home = home_dir or get_codex_home()
    logs_db = home / "logs_2.sqlite"

    task_summary = f"Codex session {session_id}"
    completed_work = []
    objective = ""

    if logs_db.is_file():
        try:
            conn = sqlite3.connect(str(logs_db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            if "logs" in tables:
                cursor.execute(
                    "SELECT message, payload FROM logs WHERE session_id = ? ORDER BY id ASC LIMIT 50",
                    (session_id,),
                )
                for r in cursor.fetchall():
                    msg = str(r["message"] or "")
                    if not objective and ("user" in msg.lower() or "prompt" in msg.lower()):
                        objective = msg
                    if msg:
                        completed_work.append(msg[:80])
            conn.close()
        except Exception:
            pass

    ctx = SessionContext(
        task_summary=task_summary,
        original_objective=objective,
        completed_work=completed_work[-10:],
    )

    return NormalizedSession(
        id=f"codex-{session_id}",
        source_provider="codex",
        source_session_id=session_id,
        project="codex",
        context=ctx,
        transcript_file=str(logs_db) if logs_db.is_file() else None,
    )
