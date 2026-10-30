"""Central Memory Hub service."""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pab.core.config import ConfigManager
from pab.core.db import Database
from pab.core.models.memory import MemoryItem, MemoryScope
from pab.memory.dedup import compute_memory_hash, find_duplicates
from pab.memory.search import search_memories
from pab.providers.detector import ProviderRegistry


class MemoryHub:
    """Multi-tier Memory Hub with deduplication, search, and provenance tracking."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config = config_manager or ConfigManager()
        self.db = Database(self.config.db_path)
        self.providers = ProviderRegistry(workspace_root=self.config.root.parent)

    def list_memories(self, scope: Optional[str] = None) -> List[MemoryItem]:
        items = []
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            if scope:
                cursor.execute("SELECT * FROM memories WHERE scope = ? ORDER BY updated_at DESC", (scope,))
            else:
                cursor.execute("SELECT * FROM memories ORDER BY updated_at DESC")
            for row in cursor.fetchall():
                d = dict(row)
                items.append(
                    MemoryItem(
                        id=d["id"],
                        scope=d["scope"],
                        title=d["title"],
                        content=d["content"],
                        content_hash=d["content_hash"],
                        source_provider=d.get("source_provider"),
                        source_path=d.get("source_path"),
                        project_id=d.get("project_id"),
                        agent_id=d.get("agent_id"),
                        untrusted=bool(d.get("untrusted")),
                        created_at=d["created_at"],
                        updated_at=d["updated_at"],
                    )
                )
        return items

    def add_memory(self, item: MemoryItem) -> MemoryItem:
        if not item.content_hash:
            item.content_hash = compute_memory_hash(item.content)

        scope_dir = self.config.memory_dir / item.scope
        scope_dir.mkdir(parents=True, exist_ok=True)
        file_path = scope_dir / f"{item.id}.md"

        header = f"# {item.title}\n<!-- Source: {item.source_provider or 'PAB'}, Scope: {item.scope}, Untrusted: {item.untrusted} -->\n\n"
        file_path.write_text(header + item.content, encoding="utf-8")

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO memories (
                    id, scope, title, content, content_hash, source_provider,
                    source_path, project_id, agent_id, untrusted, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.scope,
                    item.title,
                    item.content,
                    item.content_hash,
                    item.source_provider,
                    item.source_path or str(file_path),
                    item.project_id,
                    item.agent_id,
                    1 if item.untrusted else 0,
                    item.created_at,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

        self.db.record_audit(
            event_type="add_memory",
            resource_type="memory",
            resource_id=item.id,
            provider=item.source_provider,
            details={"title": item.title, "scope": item.scope, "untrusted": item.untrusted},
        )
        return item

    def search(self, query: str, scope: Optional[str] = None) -> List[MemoryItem]:
        all_items = self.list_memories(scope=scope)
        return search_memories(all_items, query)

    def import_from_provider(self, provider_name: str) -> Dict[str, Any]:
        """Import memories from a provider, tagging as untrusted until reviewed."""
        imported_items = []
        if provider_name == "openclaw":
            from pab.providers.openclaw.memory import list_openclaw_memories
            imported_items = list_openclaw_memories()
        elif provider_name == "codex":
            from pab.providers.codex.memory import list_codex_memories
            imported_items = list_codex_memories()
        elif provider_name == "claude":
            from pab.providers.claude.memory import list_claude_memories
            imported_items = list_claude_memories()
        elif provider_name == "agy":
            from pab.providers.agy.memory import list_agy_memories
            imported_items = list_agy_memories()

        added = 0
        skipped = 0
        existing_hashes = {m.content_hash for m in self.list_memories()}

        for item in imported_items:
            item.untrusted = True  # Security rule: imported memories marked untrusted until reviewed
            h = item.content_hash or compute_memory_hash(item.content)
            if h in existing_hashes:
                skipped += 1
                continue
            self.add_memory(item)
            existing_hashes.add(h)
            added += 1

        return {
            "provider": provider_name,
            "total_found": len(imported_items),
            "added": added,
            "skipped_duplicates": skipped,
        }

    def backup_memories(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_dir = self.config.backups_dir / f"memory_backup_{timestamp}"
        shutil.copytree(self.config.memory_dir, backup_dir)
        self.db.record_audit(
            event_type="backup_memory",
            resource_type="memory",
            resource_id=backup_dir.name,
            details={"backup_path": str(backup_dir)},
        )
        return backup_dir
