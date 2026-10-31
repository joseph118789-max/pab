"""MiniMax Coding (mcode) agent definition compilation and inventory."""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pab.core.models.agent import CanonicalAgentDefinition
from pab.providers.minimax.config import get_minimax_home


def list_minimax_agents(
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    home = home_dir or get_minimax_home()
    agents = []
    dirs_to_check = [home / "agents"]
    if workspace_root:
        dirs_to_check.append(workspace_root / ".minimax" / "agents")

    seen = set()
    for directory in dirs_to_check:
        if not directory.is_dir():
            continue
        for child in directory.iterdir():
            agent_file = None
            agent_id = child.name
            if child.is_dir() and (child / "agent.md").is_file():
                agent_file = child / "agent.md"
            elif child.is_file() and child.suffix == ".md":
                agent_file = child
                agent_id = child.stem

            if agent_file and agent_id not in seen:
                seen.add(agent_id)
                meta: Dict[str, Any] = {}
                try:
                    text = agent_file.read_text(encoding="utf-8")
                    if text.startswith("---"):
                        parts = text.split("---", 2)
                        if len(parts) >= 3:
                            front = yaml.safe_load(parts[1]) or {}
                            meta = {
                                "id": front.get("name", agent_id),
                                "name": front.get("x-mavis", {}).get("displayName", agent_id),
                                "description": front.get("description", ""),
                                "tools": front.get("tools", []),
                                "path": str(agent_file),
                            }
                except Exception:
                    meta = {"id": agent_id, "name": agent_id, "path": str(agent_file)}
                agents.append(meta)
    return agents


def compile_minimax_agent(
    definition: CanonicalAgentDefinition,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> Dict[str, Any]:
    home = home_dir or get_minimax_home()
    if workspace_root:
        target_dir = workspace_root / ".minimax" / "agents" / definition.id
    else:
        target_dir = home / "agents" / definition.id

    target_dir.mkdir(parents=True, exist_ok=True)
    agent_file = target_dir / "agent.md"

    # Default toolset for MiniMax Coding
    tools = [
        "read",
        "write",
        "edit",
        "bash",
        "grep",
        "glob",
    ]

    frontmatter = {
        "name": definition.id,
        "description": definition.description or definition.name,
        "tools": tools,
        "features": {
            "mavis": True,
            "delegation": False,
            "webSearch": True,
        },
        "x-mavis": {
            "displayName": definition.name,
        },
    }

    body = (
        f"# Role: {definition.name}\n\n"
        f"You are {definition.name}. Role: {definition.identity.role}.\n\n"
        f"## Persona\n{definition.identity.persona}\n\n"
        f"## Objective\n{definition.identity.objective}\n\n"
        f"## Guidelines\n"
        f"- Style: {definition.preferences.response_style}\n"
        f"- Execute tasks cleanly within stated boundaries.\n"
    )

    content = f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n{body}\n"
    agent_file.write_text(content, encoding="utf-8")

    return {
        "id": definition.id,
        "name": definition.name,
        "path": str(agent_file),
        "status": "deployed",
    }


def delete_minimax_agent(
    agent_id: str,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> bool:
    home = home_dir or get_minimax_home()
    deleted = False
    candidates = []
    if workspace_root:
        candidates.append(workspace_root / ".minimax" / "agents" / agent_id)
    candidates.append(home / "agents" / agent_id)

    for c in candidates:
        if c.is_dir():
            shutil.rmtree(c, ignore_errors=True)
            deleted = True
        elif c.is_file():
            c.unlink(missing_ok=True)
            deleted = True
    return deleted
