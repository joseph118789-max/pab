"""Pi Coding Agent session discovery and export."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pab.core.models.session import NormalizedSession, SessionContext
from pab.providers.pi.config import get_pi_sessions_dir


def list_pi_sessions(home_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Discover sessions created by Pi."""
    sessions_dir = get_pi_sessions_dir()
    sessions = []
    if not sessions_dir.is_dir():
        return sessions

    for item in sessions_dir.rglob("*.jsonl"):
        stat = item.stat()
        rel_parts = item.relative_to(sessions_dir).parts
        project_name = rel_parts[0] if len(rel_parts) > 1 else ""
        sessions.append({
            "id": f"pi:{item.stem}",
            "project": project_name,
            "session_path": str(item),
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
        })
    return sessions


def export_pi_session(
    session_id: str,
    home_dir: Optional[Path] = None,
) -> Optional[NormalizedSession]:
    """Export and normalize a Pi session."""
    clean_id = session_id.removeprefix("pi:")
    sessions_dir = get_pi_sessions_dir()
    target_file = None
    if sessions_dir.is_dir():
        for f in sessions_dir.rglob("*.jsonl"):
            if f.stem == clean_id or f.name == clean_id:
                target_file = f
                break

    if not target_file or not target_file.is_file():
        return None

    task_summary = f"Pi session {clean_id}"
    objective = ""
    completed_work = []

    try:
        lines = target_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line.strip():
                continue
            entry = json.loads(line)
            role = entry.get("role") or entry.get("type")
            content = entry.get("content") or entry.get("text") or ""
            if role in ["user", "prompt"] and not objective:
                objective = str(content)[:200]
            elif role in ["assistant", "model"]:
                task_summary = str(content)[:200]
    except Exception:
        pass

    ctx = SessionContext(
        task_summary=task_summary,
        original_objective=objective,
        completed_work=completed_work,
    )
    return NormalizedSession(
        id=f"pi-{clean_id}",
        source_provider="pi",
        source_session_id=clean_id,
        project=target_file.parent.name if target_file else "",
        context=ctx,
    )
