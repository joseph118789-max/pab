"""OpenClaw skill deployment and inventory."""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pab.core.models.skill import CanonicalSkill
from pab.providers.openclaw.config import get_openclaw_home


def list_openclaw_skills(home_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    home = home_dir or get_openclaw_home()
    skills = []
    # Search in plugin-skills and agent skills
    search_dirs = [
        home / "plugin-skills",
        home / "skill-workshop",
    ]
    agents_dir = home / "agents"
    if agents_dir.is_dir():
        for ad in agents_dir.iterdir():
            if ad.is_dir() and (ad / "skills").is_dir():
                search_dirs.append(ad / "skills")

    seen = set()
    for s_dir in search_dirs:
        if not s_dir.is_dir():
            continue
        for child in s_dir.iterdir():
            if child.is_dir() and (child / "SKILL.md").is_file():
                name = child.name
                if name not in seen:
                    seen.add(name)
                    desc = ""
                    try:
                        content = (child / "SKILL.md").read_text(encoding="utf-8")
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
                        "path": str(child),
                    })
    return skills


def install_openclaw_skill(
    skill: CanonicalSkill,
    agent_id: Optional[str] = None,
    home_dir: Optional[Path] = None,
) -> bool:
    home = home_dir or get_openclaw_home()
    target_dirs = []
    if agent_id:
        target_dirs.append(home / "agents" / agent_id / "skills" / skill.manifest.name)
    else:
        target_dirs.append(home / "plugin-skills" / skill.manifest.name)
        workspace_skills = home / "workspace" / "skills"
        if workspace_skills.is_dir():
            target_dirs.append(workspace_skills / skill.manifest.name)

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


def remove_openclaw_skill(skill_name: str, agent_id: Optional[str] = None, home_dir: Optional[Path] = None) -> bool:
    home = home_dir or get_openclaw_home()
    removed = False
    candidates = []
    if agent_id:
        candidates.append(home / "agents" / agent_id / "skills" / skill_name)
    candidates.append(home / "plugin-skills" / skill_name)

    for c in candidates:
        if c.is_dir():
            shutil.rmtree(c, ignore_errors=True)
            removed = True
    return removed
