"""Unit tests for Instruction and AGENTS.md Manager."""

from pathlib import Path
from pab.core.config import ConfigManager
from pab.instructions.differ import compare_instruction_texts
from pab.instructions.manager import InstructionManager
from pab.instructions.merger import merge_instruction_rules


def test_instruction_comparison_and_conflict_detection():
    doc_a = (
        "# General\nVerify all changes.\n\n"
        "# Security\nAlways require interactive approval before writing production databases.\n"
    )
    doc_b = (
        "# General\nVerify all changes.\n\n"
        "# Security\nRun commands in automatic non-interactive mode directly.\n"
    )

    res = compare_instruction_texts(doc_a, doc_b, label_a="DocA", label_b="DocB")
    assert res["is_identical"] is False
    assert "general" in res["matching_sections"]
    assert any(c["section"] == "security" for c in res["conflicting_sections"])


def test_non_destructive_merging(tmp_path: Path, config_mgr: ConfigManager):
    im = InstructionManager(config_mgr)
    canonical = (
        "# Core Directives\n- Deterministic code\n\n"
        "# Tool Policies\n- Safe non-interactive flags\n"
    )
    im.update_canonical(canonical)

    # Native existing with provider marker
    native_existing = (
        "# Core Directives\n- Deterministic code\n\n"
        "# Custom [CLAUDE]\n- Claude specific formatting conventions\n"
    )
    merged = merge_instruction_rules(canonical, native_existing, "claude")
    assert "Deterministic code" in merged
    assert "Claude specific formatting conventions" in merged
    assert "Managed by PersonaOS Agent Bridge" in merged


def test_export_for_all_providers(tmp_path: Path, config_mgr: ConfigManager):
    im = InstructionManager(config_mgr)
    target_dir = tmp_path / "instructions_export"

    dest_claude = im.export_for_provider("claude", target_dir)
    assert dest_claude.name == "CLAUDE.md"
    assert dest_claude.is_file()

    dest_agy = im.export_for_provider("agy", target_dir)
    assert dest_agy.name == "GEMINI.md"
    assert dest_agy.is_file()

    dest_codex = im.export_for_provider("codex", target_dir)
    assert dest_codex.name == "AGENTS.md"
    assert dest_codex.is_file()
