"""DeepSeek Shell (DSH) profile and agent management."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from pab.core.models.agent import CanonicalAgentDefinition
from pab.providers.dsh.config import get_dsh_home, get_dsh_profiles_dir


def list_dsh_agents(
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """List DSH profiles and agent configurations."""
    home = home_dir or get_dsh_home()
    agents = []

    dirs_to_check = [home / "profiles", home / "agents"]
    if workspace_root:
        dirs_to_check.append(workspace_root / ".dsh" / "agents")

    seen = set()
    for d in dirs_to_check:
        if not d.is_dir():
            continue
        for item in d.iterdir():
            if item.is_dir():
                agent_id = item.name
                if agent_id not in seen:
                    seen.add(agent_id)
                    patch_file = item / "cordis.patch.yml"
                    desc = ""
                    role = "DeepSeek Assistant"
                    if patch_file.is_file():
                        try:
                            content = yaml.safe_load(patch_file.read_text(encoding="utf-8")) or {}
                            desc = content.get("description", "")
                            role = content.get("role", role)
                        except Exception:
                            pass
                    agents.append({
                        "id": agent_id,
                        "name": agent_id,
                        "description": desc,
                        "role": role,
                        "config_dir": str(item),
                    })
    return agents


def compile_dsh_agent(
    definition: CanonicalAgentDefinition,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Compile canonical agent into DSH profile layer."""
    home = home_dir or get_dsh_home()
    target_dir = home / "profiles" / definition.id
    if workspace_root:
        target_dir = workspace_root / ".dsh" / "agents" / definition.id

    target_dir.mkdir(parents=True, exist_ok=True)

    # Write cordis.patch.yml
    patch_file = target_dir / "cordis.patch.yml"
    patch_data = {
        "name": definition.name,
        "description": definition.description,
        "role": definition.identity.role,
        "system_prompt": definition.instructions.system_prompt,
        "skills": definition.capabilities.skills,
        "model": definition.preferences.model if definition.preferences.model != "inherit" else "deepseek-coder",
    }
    patch_file.write_text(yaml.safe_dump(patch_data, sort_keys=False), encoding="utf-8")

    # Write package.json if not present
    pkg_file = target_dir / "package.json"
    if not pkg_file.is_file():
        pkg_data = {
            "name": f"dsh-profile-{definition.id}",
            "version": "1.0.0",
            "private": True,
            "dsh": {
                "profile": {
                    "bundles": ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-headless"],
                }
            },
        }
        pkg_file.write_text(json.dumps(pkg_data, indent=2), encoding="utf-8")

    return {"path": str(target_dir), "agent_id": definition.id}


def delete_dsh_agent(
    agent_id: str,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> bool:
    """Delete a DSH profile or agent."""
    import shutil
    home = home_dir or get_dsh_home()
    deleted = False
    candidates = [
        home / "profiles" / agent_id,
        home / "agents" / agent_id,
    ]
    if workspace_root:
        candidates.append(workspace_root / ".dsh" / "agents" / agent_id)

    for c in candidates:
        if c.is_dir():
            shutil.rmtree(c, ignore_errors=True)
            deleted = True
    return deleted
