"""MiniMax Coding (mcode) skill management."""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pab.core.models.skill import CanonicalSkill
from pab.providers.minimax.config import get_minimax_home


def list_minimax_skills(
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    home = home_dir or get_minimax_home()
    skills = []
    dirs_to_check = [
        home / "skills",
        home / ".builtin-skills",
    ]
    if workspace_root:
        dirs_to_check.append(workspace_root / ".minimax" / "skills")

    seen = set()
    for d in dirs_to_check:
        if not d.is_dir():
            continue
        for item in d.iterdir():
            if item.is_dir() and (item / "SKILL.md").is_file():
                name = item.name
                if name not in seen:
                    seen.add(name)
                    desc = ""
                    try:
                        content = (item / "SKILL.md").read_text(encoding="utf-8")
                        if content.startswith("---"):
                            parts = content.split("---", 2)
                            if len(parts) >= 3:
                                meta = yaml.safe_load(parts[1]) or {}
                                desc = meta.get("description", "")
                    except Exception:
                        pass
                    skills.append({
                        "name": name,
                        "description": desc,
                        "path": str(item / "SKILL.md"),
                    })
    return skills


def install_minimax_skill(
    skill: CanonicalSkill,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> bool:
    target_dirs = []
    skill_name = skill.manifest.name
    if workspace_root:
        target_dirs.append(workspace_root / ".minimax" / "skills" / skill_name)
    home = home_dir or get_minimax_home()
    target_dirs.append(home / "skills" / skill_name)

    frontmatter = yaml.safe_dump(skill.manifest.model_dump(), sort_keys=False)
    content = f"---\n{frontmatter}---\n\n{skill.body}\n"

    for target_dir in target_dirs:
        target_dir.mkdir(parents=True, exist_ok=True)
        skill_md = target_dir / "SKILL.md"
        skill_md.write_text(content, encoding="utf-8")

        if skill.source_path:
            src = Path(skill.source_path)
            for folder in ["scripts", "references", "assets"]:
                s_folder = src / folder
                if s_folder.is_dir():
                    d_folder = target_dir / folder
                    shutil.copytree(s_folder, d_folder, dirs_exist_ok=True)
    return True


def remove_minimax_skill(
    skill_name: str,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> bool:
    removed = False
    candidates = []
    if workspace_root:
        candidates.append(workspace_root / ".minimax" / "skills" / skill_name)
    home = home_dir or get_minimax_home()
    candidates.append(home / "skills" / skill_name)

    for c in candidates:
        if c.is_dir():
            shutil.rmtree(c, ignore_errors=True)
            removed = True
    return removed
