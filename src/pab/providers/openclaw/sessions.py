"""OpenClaw session discovery and export."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.session import NormalizedSession, SessionContext
from pab.providers.openclaw.config import get_openclaw_home


def list_openclaw_sessions(home_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    home = home_dir or get_openclaw_home()
    sessions = []
    agents_dir = home / "agents"
    if not agents_dir.is_dir():
        return sessions

    for ad in agents_dir.iterdir():
        if not ad.is_dir():
            continue
        agent_id = ad.name
        sess_dir = ad / "sessions"
        if not sess_dir.is_dir():
            continue
        for sf in sess_dir.iterdir():
            if sf.is_file() and sf.suffix in [".json", ".jsonl"]:
                sessions.append({
                    "id": f"{agent_id}:{sf.stem}",
                    "agent_id": agent_id,
                    "session_file": str(sf),
                    "size_bytes": sf.stat().st_size,
                    "modified_at": sf.stat().st_mtime,
                })
    return sessions


def export_openclaw_session(
    session_id: str,
    home_dir: Optional[Path] = None,
) -> Optional[NormalizedSession]:
    home = home_dir or get_openclaw_home()
    parts = session_id.split(":", 1)
    if len(parts) == 2:
        agent_id, raw_id = parts
    else:
        agent_id = "main"
        raw_id = session_id

    session_path = home / "agents" / agent_id / "sessions" / f"{raw_id}.json"
    if not session_path.is_file():
        session_path = home / "agents" / agent_id / "sessions" / f"{raw_id}.jsonl"

    if not session_path.is_file():
        return None

    task_summary = f"Session {session_id} from OpenClaw agent {agent_id}"
    completed_work = []
    objective = ""

    try:
        content = session_path.read_text(encoding="utf-8")
        if session_path.suffix == ".json":
            data = json.loads(content)
            objective = data.get("objective") or data.get("prompt") or ""
            task_summary = data.get("summary") or task_summary
            completed_work = data.get("completed_steps") or []
    except Exception:
        pass

    ctx = SessionContext(
        task_summary=task_summary,
        original_objective=objective,
        completed_work=completed_work,
    )

    return NormalizedSession(
        id=f"openclaw-{agent_id}-{raw_id}",
        source_provider="openclaw",
        source_session_id=session_id,
        project="openclaw",
        context=ctx,
        transcript_file=str(session_path),
    )
