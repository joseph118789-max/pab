"""Antigravity memory and rule discovery."""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.memory import MemoryItem
from pab.providers.agy.config import get_agy_cli_dir, get_agy_config_dir


def list_agy_memories(
    config_dir: Optional[Path] = None,
    cli_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> List[MemoryItem]:
    memories = []
    # 1. Project rules and instruction files
    if workspace_root:
        for fname in ["GEMINI.md", "AGENTS.md"]:
            f = workspace_root / fname
            if f.is_file():
                try:
                    text = f.read_text(encoding="utf-8")
                    content_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
                    memories.append(
                        MemoryItem(
                            id=f"agy-rule-{fname.lower().replace('.', '-')}",
                            title=fname,
                            content=text,
                            scope="project",
                            source_provider="agy",
                            source_path=str(f),
                            content_hash=content_hash,
                            untrusted=False,
                        )
                    )
                except Exception:
                    pass

    # 2. Brain artifacts in CLI directory
    c_dir = cli_dir or get_agy_cli_dir()
    brain_dir = c_dir / "brain"
    if brain_dir.is_dir():
        for conv_dir in brain_dir.iterdir():
            if conv_dir.is_dir():
                for md_file in conv_dir.glob("*.md"):
                    try:
                        text = md_file.read_text(encoding="utf-8")
                        content_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
                        memories.append(
                            MemoryItem(
                                id=f"agy-artifact-{conv_dir.name}-{md_file.stem}",
                                title=f"Artifact: {md_file.name} ({conv_dir.name[:8]})",
                                content=text,
                                scope="handoff",
                                source_provider="agy",
                                source_path=str(md_file),
                                content_hash=content_hash,
                                untrusted=False,
                            )
                        )
                    except Exception:
                        continue
    return memories
