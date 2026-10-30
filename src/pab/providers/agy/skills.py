"""Antigravity skill management and progressive disclosure."""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pab.core.models.skill import CanonicalSkill
from pab.providers.agy.config import get_agy_cli_dir, get_agy_config_dir


def list_agy_skills(config_dir: Optional[Path] = None, workspace_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    skills = []
    dirs_to_check = []

    # Global config skills
    cfg = config_dir or get_agy_config_dir()
    if (cfg / "skills").is_dir():
        dirs_to_check.append(cfg / "skills")

    # Workspace skills
    if workspace_root and (workspace_root / ".agents" / "skills").is_dir():
        dirs_to_check.append(workspace_root / ".agents" / "skills")

    # CLI builtin skills
    cli_dir = get_agy_cli_dir()
    for sub in ["skills", "builtin/skills"]:
        cand = cli_dir / sub
        if cand.is_dir():
            dirs_to_check.append(cand)

    seen = set()
    for d in dirs_to_check:
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
                        "path": str(item),
                    })
    return skills


def install_agy_skill(
    skill: CanonicalSkill,
    config_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> bool:
    if workspace_root:
        target_dir = workspace_root / ".agents" / "skills" / skill.manifest.name
    else:
        cfg = config_dir or get_agy_config_dir()
        target_dir = cfg / "skills" / skill.manifest.name

    target_dir.mkdir(parents=True, exist_ok=True)
    skill_md = target_dir / "SKILL.md"

    frontmatter = yaml.safe_dump(skill.manifest.model_dump(), sort_keys=False)
    content = f"---\n{frontmatter}---\n\n{skill.body}\n"
    skill_md.write_text(content, encoding="utf-8")

    if skill.source_path:
        src = Path(skill.source_path)
        for folder in ["scripts", "references", "assets"]:
            s_folder = src / folder
            if s_folder.is_dir():
                d_folder = target_dir / folder
                shutil.copytree(s_folder, d_folder, dirs_exist_ok=True)
    return True


def remove_agy_skill(
    skill_name: str,
    config_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> bool:
    removed = False
    candidates = []
    if workspace_root:
        candidates.append(workspace_root / ".agents" / "skills" / skill_name)
    cfg = config_dir or get_agy_config_dir()
    candidates.append(cfg / "skills" / skill_name)

    for c in candidates:
        if c.is_dir():
            shutil.rmtree(c, ignore_errors=True)
            removed = True
    return removed
