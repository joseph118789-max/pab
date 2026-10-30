"""Instruction comparison, diffing, and conflict detection."""

import difflib
import re
from typing import Any, Dict, List


def parse_instruction_rules(text: str) -> List[Dict[str, str]]:
    """Extract individual rule sections from Markdown instruction files."""
    rules = []
    current_title = "General"
    current_lines = []

    for line in text.splitlines():
        if line.startswith("#"):
            if current_lines:
                rules.append({
                    "title": current_title,
                    "content": "\n".join(current_lines).strip(),
                })
                current_lines = []
            current_title = line.lstrip("#").strip()
        else:
            current_lines.append(line)

    if current_lines:
        rules.append({
            "title": current_title,
            "content": "\n".join(current_lines).strip(),
        })

    return rules


def compare_instruction_texts(text_a: str, text_b: str, label_a: str = "A", label_b: str = "B") -> Dict[str, Any]:
    """Compare two instruction texts, returning unified diff, overlapping rules, and conflicts."""
    diff = list(
        difflib.unified_diff(
            text_a.splitlines(keepends=True),
            text_b.splitlines(keepends=True),
            fromfile=label_a,
            tofile=label_b,
        )
    )

    rules_a = {r["title"].lower(): r["content"] for r in parse_instruction_rules(text_a)}
    rules_b = {r["title"].lower(): r["content"] for r in parse_instruction_rules(text_b)}

    common_keys = set(rules_a.keys()).intersection(rules_b.keys())
    conflicts = []
    matches = []

    for k in common_keys:
        if rules_a[k].strip() == rules_b[k].strip():
            matches.append(k)
        else:
            conflicts.append({
                "section": k,
                f"content_{label_a}": rules_a[k],
                f"content_{label_b}": rules_b[k],
            })

    return {
        "diff": "".join(diff),
        "is_identical": len(diff) == 0,
        "matching_sections": matches,
        "conflicting_sections": conflicts,
    }
