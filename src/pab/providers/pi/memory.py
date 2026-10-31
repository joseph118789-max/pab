"""Pi memory reader."""

from pathlib import Path
from typing import List, Optional
from pab.core.models.memory import MemoryItem
from pab.providers.pi.config import get_pi_home


def list_pi_memories(
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> List[MemoryItem]:
    """Collect memory from Pi."""
    home = home_dir or get_pi_home()
    memories = []
    mem_dir = home / "memory"
    if mem_dir.is_dir():
        for mf in mem_dir.glob("*.md"):
            memories.append(MemoryItem(
                id=f"pi-mem-{mf.stem}",
                title=mf.stem.replace("-", " ").title(),
                content=mf.read_text(encoding="utf-8"),
                scope="project",
                source_provider="pi",
                untrusted=True,
            ))
    return memories
