"""Validation for Open Agent Skills (SKILL.md)."""

import re
from pathlib import Path
from typing import List
from pab.core.models.skill import CanonicalSkill

KEBAB_CASE_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_skill_structure(skill: CanonicalSkill) -> List[str]:
    """Validate canonical skill metadata, structure, and required resources."""
    issues = []
    manifest = skill.manifest

    # 1. Name validation
    if not manifest.name:
        issues.append("Skill manifest 'name' is required.")
    elif not KEBAB_CASE_PATTERN.match(manifest.name):
        issues.append(f"Skill name '{manifest.name}' must be kebab-case (lowercase alphanumeric with hyphens).")

    # 2. Description validation
    if not manifest.description or len(manifest.description.strip()) < 10:
        issues.append("Skill manifest 'description' must provide clear context (at least 10 characters).")

    # 3. Body validation
    if not skill.body or len(skill.body.strip()) < 20:
        issues.append("Skill body must provide operational guidance (at least 20 characters).")

    # 4. Verify referenced scripts exist on disk if source_path is set
    if skill.source_path:
        src = Path(skill.source_path)
        for s in skill.scripts:
            f = src / s.relative_path
            if not f.is_file():
                issues.append(f"Referenced script '{s.relative_path}' was not found on disk.")
        for r in skill.references:
            f = src / r.relative_path
            if not f.is_file():
                issues.append(f"Referenced doc '{r.relative_path}' was not found on disk.")

    return issues
