"""OpenClaw session discovery and export."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.session import NormalizedSession, SessionContext
from pab.providers.openclaw.config import get_openclaw_home


"""OpenClaw session discovery and export."""

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from pab.core.models.session import NormalizedSession, SessionContext
from pab.providers.openclaw.config import get_openclaw_home


def _resolve_session_identity(
    session_id: str,
    home: Path,
) -> Tuple[str, str, Optional[str], Optional[str]]:
    """
    Resolve session_id or alias (e.g. telegram:group:-5036746892, UUID, or agent:session)
    into (agent_id, raw_session_id, conversation_label, project_hint).
    """
    agent_id = "main"
    raw_id = session_id
    label = None
    project_hint = None

    # Handle agent prefix like main:8278155c... or main:telegram:...
    if ":" in session_id:
        p0, rest = session_id.split(":", 1)
        if (home / "agents" / p0).is_dir():
            agent_id = p0
            raw_id = rest

    agents_dir = home / "agents"
    if not agents_dir.is_dir():
        return agent_id, raw_id, label, project_hint

    # Candidate agents to search
    candidate_agents = (
        [agent_id]
        if (agents_dir / agent_id).is_dir()
        else [d.name for d in agents_dir.iterdir() if d.is_dir()]
    )

    tokens = [raw_id]
    if ":" in raw_id:
        tokens.append(raw_id.split(":")[-1])
    tokens = [t for t in tokens if t]

    for ag in candidate_agents:
        db_path = agents_dir / ag / "agent" / "openclaw-agent.sqlite"
        if not db_path.is_file():
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            c = conn.cursor()

            # 1. Direct session_id check
            c.execute("SELECT session_id FROM session_windows WHERE session_id = ?", (raw_id,))
            r = c.fetchone()
            if r:
                # Retrieve conversation label if exists
                c.execute(
                    """
                    SELECT c.label FROM session_conversations sc
                    JOIN conversations c ON sc.conversation_id = c.conversation_id
                    WHERE sc.session_id = ?
                    ORDER BY sc.last_seen_at DESC LIMIT 1
                    """,
                    (r[0],),
                )
                lbl_row = c.fetchone()
                if lbl_row and lbl_row[0]:
                    label = lbl_row[0]
                conn.close()
                return ag, r[0], label, _extract_project_from_label(label)

            # 2. Check by tokens in peer_id, delivery_target, conversation_id, or label
            for tok in tokens:
                c.execute(
                    """
                    SELECT sc.session_id, c.label
                    FROM session_conversations sc
                    JOIN conversations c ON sc.conversation_id = c.conversation_id
                    WHERE c.peer_id LIKE ? OR c.delivery_target LIKE ? OR c.conversation_id = ? OR c.label LIKE ?
                    ORDER BY sc.last_seen_at DESC LIMIT 1
                    """,
                    (f"%{tok}%", f"%{tok}%", tok, f"%{tok}%"),
                )
                r = c.fetchone()
                if r:
                    conn.close()
                    lbl = r[1]
                    return ag, r[0], lbl, _extract_project_from_label(lbl)

            conn.close()
        except Exception:
            pass

    return agent_id, raw_id, label, project_hint


def _extract_project_from_label(label: Optional[str]) -> Optional[str]:
    if not label:
        return None
    # E.g. telegram:g-projects-ansible-hardening -> ansible-hardening
    # or telegram:g-ansible-hardening -> ansible-hardening
    clean = label.replace("telegram:g-projects-", "").replace("telegram:g-", "").replace("telegram:", "")
    return clean if clean else None


def list_openclaw_sessions(home_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    home = home_dir or get_openclaw_home()
    sessions = []
    seen_ids = set()
    agents_dir = home / "agents"
    if not agents_dir.is_dir():
        return sessions

    for ad in agents_dir.iterdir():
        if not ad.is_dir():
            continue
        agent_id = ad.name
        sess_dir = ad / "sessions"
        if sess_dir.is_dir():
            for sf in sess_dir.iterdir():
                if sf.is_file() and sf.suffix in [".json", ".jsonl"]:
                    sid = f"{agent_id}:{sf.stem}"
                    seen_ids.add(sid)
                    sessions.append({
                        "id": sid,
                        "agent_id": agent_id,
                        "session_file": str(sf),
                        "size_bytes": sf.stat().st_size,
                        "modified_at": sf.stat().st_mtime,
                    })

        # Also discover active sessions from SQLite
        db_path = ad / "agent" / "openclaw-agent.sqlite"
        if db_path.is_file():
            try:
                conn = sqlite3.connect(str(db_path))
                c = conn.cursor()
                c.execute(
                    """
                    SELECT sc.session_id, c.label, c.peer_id, sc.last_seen_at
                    FROM session_conversations sc
                    JOIN conversations c ON sc.conversation_id = c.conversation_id
                    ORDER BY sc.last_seen_at DESC LIMIT 50
                    """
                )
                for r in c.fetchall():
                    real_sid = r[0]
                    canon_id = f"{agent_id}:{real_sid}"
                    label = r[1] or ""
                    peer_id = r[2] or ""
                    if canon_id not in seen_ids:
                        seen_ids.add(canon_id)
                        sessions.append({
                            "id": canon_id,
                            "agent_id": agent_id,
                            "session_file": f"sqlite://{agent_id}/{real_sid}",
                            "size_bytes": 0,
                            "modified_at": r[3] / 1000.0 if r[3] else 0,
                            "label": label,
                            "peer_id": peer_id,
                            "project": _extract_project_from_label(label) or "openclaw",
                        })
                conn.close()
            except Exception:
                pass

    return sessions


def export_openclaw_session(
    session_id: str,
    home_dir: Optional[Path] = None,
) -> Optional[NormalizedSession]:
    home = home_dir or get_openclaw_home()
    agent_id, raw_id, label, project_hint = _resolve_session_identity(session_id, home)

    sess_dir = home / "agents" / agent_id / "sessions"
    session_path = sess_dir / f"{raw_id}.json"
    if not session_path.is_file():
        session_path = sess_dir / f"{raw_id}.jsonl"

    # Check trajectory pointer file
    if not session_path.is_file():
        pointer_file = sess_dir / f"{raw_id}.trajectory-path.json"
        if pointer_file.is_file():
            try:
                pdata = json.loads(pointer_file.read_text(encoding="utf-8"))
                rf = Path(pdata.get("runtimeFile", ""))
                if rf.is_file():
                    session_path = rf
            except Exception:
                pass

    # Check backup files if active jsonl does not exist
    if not session_path.is_file():
        bak_matches = list(sess_dir.glob(f"{raw_id}.jsonl.bak*"))
        if bak_matches:
            session_path = sorted(bak_matches, key=lambda f: f.stat().st_mtime, reverse=True)[0]

    # If still not found on disk, dump from SQLite transcript_events
    if not session_path.is_file():
        db_path = home / "agents" / agent_id / "agent" / "openclaw-agent.sqlite"
        if db_path.is_file():
            try:
                conn = sqlite3.connect(str(db_path))
                c = conn.cursor()
                c.execute(
                    "SELECT event_json FROM transcript_events WHERE session_id = ? ORDER BY seq ASC",
                    (raw_id,),
                )
                rows = c.fetchall()
                conn.close()
                if rows:
                    sess_dir.mkdir(parents=True, exist_ok=True)
                    out_jsonl = sess_dir / f"{raw_id}.jsonl"
                    with out_jsonl.open("w", encoding="utf-8") as f:
                        for row in rows:
                            if row[0]:
                                f.write(row[0].strip() + "\n")
                    session_path = out_jsonl
            except Exception:
                pass

    if not session_path.is_file():
        return None

    task_summary = f"Session {raw_id} from OpenClaw agent {agent_id}"
    if label:
        task_summary = f"[{label}] {task_summary}"
    completed_work = []
    objective = ""

    try:
        if session_path.suffix == ".json":
            content = session_path.read_text(encoding="utf-8")
            data = json.loads(content)
            objective = data.get("objective") or data.get("prompt") or ""
            task_summary = data.get("summary") or task_summary
            completed_work = data.get("completed_steps") or []
        elif session_path.suffix in [".jsonl", ".bak"] or ".jsonl" in session_path.name:
            with session_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    if ev.get("type") == "message":
                        msg = ev.get("message", {})
                        role = msg.get("role")
                        content_obj = msg.get("content")
                        text = ""
                        if isinstance(content_obj, str):
                            text = content_obj
                        elif isinstance(content_obj, list):
                            for item in content_obj:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text += item.get("text", "") + "\n"
                        text = text.strip()
                        if not text:
                            continue

                        if role == "user":
                            # Avoid setting default media placeholders as objective if real prompt follows
                            if not objective or objective.startswith("[User sent media"):
                                if not text.startswith("[User sent media") or not objective:
                                    objective = text[:500]
                        elif role == "assistant":
                            if any(k in text for k in ["Learned:", "Completed", "Fixed", "Updated"]):
                                completed_work.append(text[:200])
                            task_summary = text[:300]
    except Exception:
        pass

    ctx = SessionContext(
        task_summary=task_summary,
        original_objective=objective,
        completed_work=completed_work[-10:],
    )

    resolved_project = project_hint or "ansible-hardening" if "ansible" in (label or "") else "openclaw"

    return NormalizedSession(
        id=f"openclaw-{agent_id}-{raw_id}",
        source_provider="openclaw",
        source_session_id=session_id,
        project=resolved_project,
        context=ctx,
        transcript_file=str(session_path),
    )

