"""OpenClaw memory discovery and export."""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.memory import MemoryItem
from pab.providers.openclaw.config import get_openclaw_home


def list_openclaw_memories(home_dir: Optional[Path] = None) -> List[MemoryItem]:
    home = home_dir or get_openclaw_home()
    memories = []

    # 1. Global memory directory
    global_mem = home / "memory"
    if global_mem.is_dir():
        for f in global_mem.iterdir():
            if f.is_file() and f.suffix == ".md":
                try:
                    text = f.read_text(encoding="utf-8")
                    content_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
                    memories.append(
                        MemoryItem(
                            id=f"openclaw-global-{f.stem}",
                            title=f.name,
                            content=text,
                            scope="global",
                            source_provider="openclaw",
                            source_path=str(f),
                            content_hash=content_hash,
                            untrusted=False,
                        )
                    )
                except Exception:
                    continue

    # 2. Agent-specific memory directories
    agents_dir = home / "agents"
    if agents_dir.is_dir():
        for ad in agents_dir.iterdir():
            if not ad.is_dir():
                continue
            agent_id = ad.name
            curated_mem = ad / "MEMORY.md"
            if curated_mem.is_file():
                try:
                    text = curated_mem.read_text(encoding="utf-8")
                    content_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
                    memories.append(
                        MemoryItem(
                            id=f"openclaw-agent-{agent_id}-curated",
                            title=f"{agent_id} Curated Memory",
                            content=text,
                            scope="agent",
                            agent_id=agent_id,
                            source_provider="openclaw",
                            source_path=str(curated_mem),
                            content_hash=content_hash,
                            untrusted=False,
                        )
                    )
                except Exception:
                    pass

            agent_daily_dir = ad / "memory"
            if agent_daily_dir.is_dir():
                for df in agent_daily_dir.iterdir():
                    if df.is_file() and df.suffix == ".md":
                        try:
                            text = df.read_text(encoding="utf-8")
                            content_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
                            memories.append(
                                MemoryItem(
                                    id=f"openclaw-agent-{agent_id}-{df.stem}",
                                    title=f"{agent_id}/{df.name}",
                                    content=text,
                                    scope="daily",
                                    agent_id=agent_id,
                                    source_provider="openclaw",
                                    source_path=str(df),
                                    content_hash=content_hash,
                                    untrusted=False,
                                )
                            )
                        except Exception:
                            continue

    return memories
