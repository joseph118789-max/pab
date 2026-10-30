"""Central Instruction and AGENTS.md Manager."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.config import ConfigManager
from pab.core.db import Database
from pab.core.models.instruction import CanonicalInstructions
from pab.instructions.differ import compare_instruction_texts
from pab.instructions.merger import merge_instruction_rules


class InstructionManager:
    """Manages canonical AGENTS.md and platform-specific instruction files."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config = config_manager or ConfigManager()
        self.db = Database(self.config.db_path)
        self.canonical_agents_md = self.config.instructions_dir / "AGENTS.md"
        self._ensure_default_instructions()

    def _ensure_default_instructions(self) -> None:
        if not self.canonical_agents_md.exists():
            default_content = (
                "# AGENTS.md — Global Autonomous Agent Guidelines\n\n"
                "## Core Directives\n"
                "- Verify paths before performing destructive operations.\n"
                "- Preserve existing documentation integrity.\n"
                "- Write deterministic, reproducible code with comprehensive test coverage.\n"
                "- Avoid modifying external authentication files or internal databases directly.\n\n"
                "## Tool & Execution Policies\n"
                "- Shell commands must use non-interactive flags wherever possible.\n"
                "- Redact secrets and sensitive tokens from logs and outputs.\n"
            )
            self.canonical_agents_md.write_text(default_content, encoding="utf-8")

    def get_canonical(self) -> str:
        return self.canonical_agents_md.read_text(encoding="utf-8")

    def update_canonical(self, content: str) -> None:
        self.canonical_agents_md.write_text(content, encoding="utf-8")
        self.db.record_audit(
            event_type="update_instructions",
            resource_type="instruction",
            resource_id="AGENTS.md",
        )

    def import_instructions(self, source_file: Path, provider: str = "generic") -> str:
        text = source_file.read_text(encoding="utf-8")
        current = self.get_canonical()
        merged = merge_instruction_rules(current, text, provider)
        self.update_canonical(merged)
        return merged

    def export_for_provider(self, provider: str, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        canonical = self.get_canonical()

        if provider == "claude":
            dest = target_dir / "CLAUDE.md"
        elif provider == "agy":
            dest = target_dir / "GEMINI.md"
        elif provider == "codex":
            dest = target_dir / "AGENTS.md"
        elif provider == "openclaw":
            dest = target_dir / "AGENTS.md"
        else:
            dest = target_dir / "AGENTS.md"

        existing = dest.read_text("utf-8") if dest.is_file() else ""
        content = merge_instruction_rules(canonical, existing, provider) if existing else canonical
        dest.write_text(content, encoding="utf-8")
        return dest

    def compare_files(self, file_a: Path, file_b: Path) -> Dict[str, Any]:
        text_a = file_a.read_text("utf-8") if file_a.is_file() else ""
        text_b = file_b.read_text("utf-8") if file_b.is_file() else ""
        return compare_instruction_texts(text_a, text_b, label_a=file_a.name, label_b=file_b.name)
