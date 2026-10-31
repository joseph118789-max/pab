"""DeepSeek Shell (DSH) session discovery and export."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from pab.core.models.session import NormalizedSession, SessionContext
from pab.providers.dsh.config import get_dsh_home


def list_dsh_sessions(home_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Discover sessions created by DSH."""
    home = home_dir or get_dsh_home()
    sessions_dir = home / "sessions"
    sessions = []
    if not sessions_dir.is_dir():
        return sessions

    for item in sessions_dir.rglob("*.json*"):
        stat = item.stat()
        sessions.append({
            "id": f"dsh:{item.stem}",
            "project": item.parent.name,
            "session_path": str(item),
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
        })
    return sessions


def export_dsh_session(
    session_id: str,
    home_dir: Optional[Path] = None,
) -> Optional[NormalizedSession]:
    """Export and normalize a DSH session."""
    clean_id = session_id.removeprefix("dsh:")
    home = home_dir or get_dsh_home()
    sessions_dir = home / "sessions"
    target_file = None
    if sessions_dir.is_dir():
        for f in sessions_dir.rglob("*"):
            if f.is_file() and (f.stem == clean_id or f.name == clean_id):
                target_file = f
                break

    if not target_file or not target_file.is_file():
        return None

    ctx = SessionContext(
        task_summary=f"DSH session {clean_id}",
        original_objective="",
        completed_work=[],
    )
    return NormalizedSession(
        id=f"dsh-{clean_id}",
        source_provider="dsh",
        source_session_id=clean_id,
        project=target_file.parent.name,
        context=ctx,
    )
