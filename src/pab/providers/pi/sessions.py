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

        # Extract session ID from filename (e.g. 2026-11-01T..._uuid.jsonl or uuid.jsonl)
        stem = item.stem
        session_id_part = stem.split("_")[-1] if "_" in stem else stem

        sessions.append({
            "id": f"pi:{session_id_part}",
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
    """Export and normalize a Pi session according to Canonical Handoff v2."""
    clean_id = session_id.removeprefix("pi:")
    sessions_dir = get_pi_sessions_dir()
    target_file = None
    if sessions_dir.is_dir():
        for f in sessions_dir.rglob("*.jsonl"):
            if clean_id in f.stem or clean_id in f.name:
                target_file = f
                break

    if not target_file or not target_file.is_file():
        return None

    task_summary = f"Pi session {clean_id}"
    objective = ""
    completed_work = []
    technical_decisions = []
    unresolved_issues = []
    important_files = set()
    raw_messages = []

    try:
        lines = target_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line.strip():
                continue
            entry = json.loads(line)
            entry_type = entry.get("type")

            if entry_type == "session":
                # Header line
                continue

            elif entry_type == "message":
                msg = entry.get("message", {})
                role = msg.get("role")
                content = msg.get("content")

                # Parse text content
                text_content = ""
                if isinstance(content, str):
                    text_content = content
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_content += part.get("text", "")
                        elif isinstance(part, str):
                            text_content += part

                if role == "user":
                    raw_messages.append({"role": "user", "content": text_content})
                    if not objective:
                        objective = text_content[:300]
                elif role == "assistant":
                    raw_messages.append({"role": "assistant", "content": text_content})
                    if text_content:
                        task_summary = text_content[:300]
                        # Look for decision or completed bullets
                        for cl in text_content.splitlines():
                            cl_strip = cl.strip()
                            if cl_strip.startswith(("- [x]", "* [x]", "Completed:", "Done:")):
                                completed_work.append(cl_strip)
                            elif "decided to" in cl_strip.lower() or "decision:" in cl_strip.lower():
                                technical_decisions.append(cl_strip)
                elif role == "toolResult":
                    tool_name = msg.get("toolName", "unknown")
                    raw_messages.append({"role": "tool_result", "tool": tool_name, "content": text_content[:200]})
                    if tool_name in ["edit", "write", "read"]:
                        # Track important files if present
                        pass
    except Exception:
        pass

    ctx = SessionContext(
        task_summary=task_summary,
        original_objective=objective,
        completed_work=completed_work,
        technical_decisions=technical_decisions,
        unresolved_issues=unresolved_issues,
        important_files=list(important_files),
    )
    return NormalizedSession(
        id=f"pi-{clean_id}",
        source_provider="pi",
        source_session_id=clean_id,
        project=target_file.parent.name if target_file else "",
        context=ctx,
        raw_transcript=json.dumps(raw_messages) if raw_messages else None,
    )
