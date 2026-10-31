"""Pi Coding Agent definition compilation and inventory."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from pab.core.models.agent import CanonicalAgentDefinition
from pab.providers.pi.config import get_pi_home


def list_pi_agents(
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """List Pi agent configurations across home and workspace."""
    home = home_dir or get_pi_home()
    agents = []

    dirs_to_check = [home / "agents"]
    if workspace_root:
        dirs_to_check.append(workspace_root / ".pi" / "agents")

    seen_ids = set()
    for d in dirs_to_check:
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.suffix in [".json", ".yaml", ".yml"]:
                agent_id = f.stem
                if agent_id not in seen_ids:
                    seen_ids.add(agent_id)
                    try:
                        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
                        agents.append({
                            "id": agent_id,
                            "name": data.get("name", agent_id),
                            "description": data.get("description", ""),
                            "role": data.get("role", "AI Coding Assistant"),
                            "config_file": str(f),
                            "skills": data.get("skills", []),
                        })
                    except Exception:
                        agents.append({
                            "id": agent_id,
                            "name": agent_id,
                            "config_file": str(f),
                        })

    return agents


def compile_pi_agent(
    definition: CanonicalAgentDefinition,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Compile canonical agent into Pi agent configuration."""
    home = home_dir or get_pi_home()
    target_dir = home / "agents"
    if workspace_root:
        target_dir = workspace_root / ".pi" / "agents"

    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / f"{definition.id}.json"

    data = {
        "id": definition.id,
        "name": definition.name,
        "description": definition.description,
        "role": definition.identity.role,
        "persona": definition.identity.persona,
        "objective": definition.identity.objective,
        "system_prompt": definition.instructions.system_prompt,
        "skills": definition.capabilities.skills,
        "model": definition.preferences.model if definition.preferences.model != "inherit" else None,
        "thinking": definition.preferences.reasoning_effort or "medium",
        "tools": definition.capabilities.tools.allowed
        if hasattr(definition.capabilities.tools, "allowed")
        else ["read", "bash", "edit", "write"],
    }

    out_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"path": str(out_file), "agent_id": definition.id}


def delete_pi_agent(
    agent_id: str,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> bool:
    """Delete a Pi agent configuration."""
    home = home_dir or get_pi_home()
    deleted = False
    candidates = [
        home / "agents" / f"{agent_id}.json",
        home / "agents" / f"{agent_id}.yaml",
    ]
    if workspace_root:
        candidates.extend([
            workspace_root / ".pi" / "agents" / f"{agent_id}.json",
            workspace_root / ".pi" / "agents" / f"{agent_id}.yaml",
        ])

    for c in candidates:
        if c.is_file():
            c.unlink()
            deleted = True
    return deleted
