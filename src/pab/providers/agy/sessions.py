"""Antigravity conversation discovery and transcript export."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.session import NormalizedSession, SessionContext
from pab.providers.agy.config import get_agy_cli_dir


def list_agy_sessions(cli_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    sessions = []
    c_dir = cli_dir or get_agy_cli_dir()
    brain_dir = c_dir / "brain"
    if not brain_dir.is_dir():
        return sessions

    for conv_dir in brain_dir.iterdir():
        if conv_dir.is_dir():
            transcript = conv_dir / ".system_generated" / "logs" / "transcript.jsonl"
            if transcript.is_file():
                sessions.append({
                    "id": conv_dir.name,
                    "conversation_id": conv_dir.name,
                    "transcript_path": str(transcript),
                    "size_bytes": transcript.stat().st_size,
                    "modified_at": transcript.stat().st_mtime,
                })
    return sessions


def export_agy_session(
    session_id: str,
    cli_dir: Optional[Path] = None,
) -> Optional[NormalizedSession]:
    c_dir = cli_dir or get_agy_cli_dir()
    conv_dir = c_dir / "brain" / session_id
    if not conv_dir.is_dir():
        return None

    transcript_file = conv_dir / ".system_generated" / "logs" / "transcript.jsonl"
    if not transcript_file.is_file():
        return None

    task_summary = f"Antigravity conversation {session_id[:8]}"
    original_objective = ""
    completed_work = []
    commands_executed = []

    try:
        with open(transcript_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                step = json.loads(line)
                if step.get("type") == "USER_INPUT" and not original_objective:
                    original_objective = step.get("content", "")
                if step.get("type") == "PLANNER_RESPONSE":
                    calls = step.get("tool_calls", [])
                    for tc in calls:
                        cmd = tc.get("CommandLine") or tc.get("command")
                        if cmd:
                            commands_executed.append(str(cmd))
                        summary = tc.get("toolSummary")
                        if summary:
                            completed_work.append(str(summary))
    except Exception:
        pass

    ctx = SessionContext(
        task_summary=task_summary,
        original_objective=original_objective,
        completed_work=completed_work[-10:],
        commands_executed=commands_executed[-10:],
    )

    return NormalizedSession(
        id=f"agy-{session_id}",
        source_provider="agy",
        source_session_id=session_id,
        project="antigravity",
        context=ctx,
        transcript_file=str(transcript_file),
    )
