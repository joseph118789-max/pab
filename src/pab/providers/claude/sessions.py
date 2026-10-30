"""Anthropic Claude Code session discovery and export."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.session import NormalizedSession, SessionContext
from pab.providers.claude.config import get_claude_home


def list_claude_sessions(home_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    home = home_dir or get_claude_home()
    sessions = []
    projects_dir = home / "projects"
    if not projects_dir.is_dir():
        return sessions

    for p in projects_dir.iterdir():
        if p.is_dir():
            for sf in p.glob("*.json"):
                sessions.append({
                    "id": f"{p.name}:{sf.stem}",
                    "project": p.name,
                    "session_path": str(sf),
                    "size_bytes": sf.stat().st_size,
                })
    return sessions


def export_claude_session(
    session_id: str,
    home_dir: Optional[Path] = None,
) -> Optional[NormalizedSession]:
    home = home_dir or get_claude_home()
    parts = session_id.split(":", 1)
    if len(parts) == 2:
        project_name, file_stem = parts
        session_file = home / "projects" / project_name / f"{file_stem}.json"
    else:
        session_file = None

    if not session_file or not session_file.is_file():
        return None

    task_summary = f"Claude session {session_id}"
    objective = ""
    completed_work = []

    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
        objective = data.get("prompt") or data.get("objective") or ""
        task_summary = data.get("summary") or task_summary
    except Exception:
        pass

    ctx = SessionContext(
        task_summary=task_summary,
        original_objective=objective,
        completed_work=completed_work,
    )

    return NormalizedSession(
        id=f"claude-{session_id.replace(':', '-')}",
        source_provider="claude",
        source_session_id=session_id,
        project=parts[0] if len(parts) == 2 else "claude",
        context=ctx,
        transcript_file=str(session_file),
    )
