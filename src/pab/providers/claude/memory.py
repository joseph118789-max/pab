"""Anthropic Claude Code memory discovery."""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.memory import MemoryItem
from pab.providers.claude.config import get_claude_home


def list_claude_memories(home_dir: Optional[Path] = None, workspace_root: Optional[Path] = None) -> List[MemoryItem]:
    home = home_dir or get_claude_home()
    memories = []

    # 1. Project CLAUDE.md
    if workspace_root:
        claude_md = workspace_root / "CLAUDE.md"
        if claude_md.is_file():
            try:
                text = claude_md.read_text(encoding="utf-8")
                content_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
                memories.append(
                    MemoryItem(
                        id="claude-project-claudemd",
                        title="Project CLAUDE.md",
                        content=text,
                        scope="project",
                        source_provider="claude",
                        source_path=str(claude_md),
                        content_hash=content_hash,
                        untrusted=False,
                    )
                )
            except Exception:
                pass

    # 2. Global projects memory
    projects_dir = home / "projects"
    if projects_dir.is_dir():
        for p in projects_dir.iterdir():
            if p.is_dir():
                for md in p.glob("*.md"):
                    try:
                        text = md.read_text(encoding="utf-8")
                        content_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
                        memories.append(
                            MemoryItem(
                                id=f"claude-proj-{p.name}-{md.stem}",
                                title=f"Claude Memory: {md.name} ({p.name})",
                                content=text,
                                scope="project",
                                source_provider="claude",
                                source_path=str(md),
                                content_hash=content_hash,
                                untrusted=False,
                            )
                        )
                    except Exception:
                        continue
    return memories
