"""DeepSeek Shell (DSH) memory reader."""

from pathlib import Path
from typing import List, Optional
from pab.core.models.memory import MemoryItem
from pab.providers.dsh.config import get_dsh_home


def list_dsh_memories(
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> List[MemoryItem]:
    """Collect memory from DSH."""
    home = home_dir or get_dsh_home()
    memories = []
    mem_dir = home / "memory"
    if mem_dir.is_dir():
        for mf in mem_dir.glob("*.md"):
            memories.append(MemoryItem(
                id=f"dsh-mem-{mf.stem}",
                title=mf.stem.replace("-", " ").title(),
                content=mf.read_text(encoding="utf-8"),
                scope="project",
                source_provider="dsh",
                untrusted=True,
            ))
    return memories
