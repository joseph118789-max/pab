"""Pi Coding Agent skill management."""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from pab.core.models.skill import CanonicalSkill
from pab.providers.pi.config import get_pi_home


def list_pi_skills(
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """List skills discovered by Pi."""
    home = home_dir or get_pi_home()
    skills = []

    dirs_to_check = [home / "skills"]
    if workspace_root:
        dirs_to_check.extend([
            workspace_root / ".pi" / "skills",
            workspace_root / "skills",
        ])

    seen = set()
    for base in dirs_to_check:
        if not base.is_dir():
            continue
        for sdir in base.iterdir():
            if sdir.is_dir() and (sdir / "SKILL.md").is_file():
                if sdir.name not in seen:
                    seen.add(sdir.name)
                    version = "1.0.0"
                    desc = ""
                    try:
                        text = (sdir / "SKILL.md").read_text(encoding="utf-8")
                        if text.startswith("---"):
                            parts = text.split("---", 2)
                            if len(parts) >= 3:
                                y = yaml.safe_load(parts[1]) or {}
                                desc = y.get("description", "")
                                version = y.get("metadata", {}).get("version") or y.get("version", "1.0.0")
                    except Exception:
                        pass
                    skills.append({
                        "name": sdir.name,
                        "description": desc,
                        "version": version,
                        "path": str(sdir),
                    })
    return skills


def install_pi_skill(
    skill: CanonicalSkill,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> bool:
    """Install an Open Agent Skill for Pi."""
    skill_name = skill.manifest.name
    home = home_dir or get_pi_home()
    target_dir = home / "skills" / skill_name
    if workspace_root:
        target_dir = workspace_root / ".pi" / "skills" / skill_name

    target_dir.mkdir(parents=True, exist_ok=True)

    if skill.source_path and Path(skill.source_path).is_dir():
        shutil.copytree(Path(skill.source_path), target_dir, dirs_exist_ok=True)
    else:
        # Generate minimal SKILL.md
        skill_md = target_dir / "SKILL.md"
        meta = yaml.safe_dump(skill.manifest.model_dump(), sort_keys=False)
        skill_md.write_text(f"---\n{meta}---\n\n{skill.body}\n", encoding="utf-8")
    return True


def remove_pi_skill(
    skill_name: str,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> bool:
    """Remove a skill from Pi."""
    home = home_dir or get_pi_home()
    removed = False
    candidates = [home / "skills" / skill_name]
    if workspace_root:
        candidates.extend([
            workspace_root / ".pi" / "skills" / skill_name,
            workspace_root / "skills" / skill_name,
        ])
    for c in candidates:
        if c.is_dir():
            shutil.rmtree(c, ignore_errors=True)
            removed = True
    return removed
