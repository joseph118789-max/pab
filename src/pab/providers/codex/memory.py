"""OpenAI Codex memory discovery and export."""

import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.memory import MemoryItem
from pab.providers.codex.config import get_codex_home


def list_codex_memories(home_dir: Optional[Path] = None) -> List[MemoryItem]:
    home = home_dir or get_codex_home()
    memories = []

    # 1. Inspect memories_1.sqlite if present
    db_path = home / "memories_1.sqlite"
    if db_path.is_file():
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Inspect table structure
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            if "stage1_outputs" in tables:
                cursor.execute("SELECT * FROM stage1_outputs LIMIT 50")
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    text = str(row_dict.get("content") or row_dict.get("output") or row_dict)
                    row_id = str(row_dict.get("id") or hashlib.sha256(text.encode("utf-8")).hexdigest()[:12])
                    content_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
                    memories.append(
                        MemoryItem(
                            id=f"codex-sqlite-{row_id}",
                            title=f"Codex Memory {row_id}",
                            content=text,
                            scope="global",
                            source_provider="codex",
                            source_path=str(db_path),
                            content_hash=content_hash,
                            untrusted=False,
                        )
                    )
            conn.close()
        except Exception:
            pass

    # 2. Inspect memories/ markdown directory if exists
    mem_dir = home / "memories"
    if mem_dir.is_dir():
        for f in mem_dir.glob("*.md"):
            try:
                text = f.read_text(encoding="utf-8")
                content_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
                memories.append(
                    MemoryItem(
                        id=f"codex-file-{f.stem}",
                        title=f.name,
                        content=text,
                        scope="project",
                        source_provider="codex",
                        source_path=str(f),
                        content_hash=content_hash,
                        untrusted=False,
                    )
                )
            except Exception:
                pass
    return memories
