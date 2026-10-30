"""Antigravity agent definition compilation and inventory."""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pab.core.models.agent import CanonicalAgentDefinition
from pab.providers.agy.config import get_agy_config_dir


def list_agy_agents(config_dir: Optional[Path] = None, workspace_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    agents = []
    dirs_to_check = []

    # 1. Global agents directory
    cfg_dir = config_dir or get_agy_config_dir()
    global_agents = cfg_dir / "agents"
    if global_agents.is_dir():
        dirs_to_check.append(global_agents)

    # 2. Workspace agents
    if workspace_root:
        ws_agents = workspace_root / ".agents" / "agents"
        if ws_agents.is_dir():
            dirs_to_check.append(ws_agents)

    seen = set()
    for directory in dirs_to_check:
        for item in directory.iterdir():
            agent_file = None
            agent_id = item.stem
            if item.is_file() and item.suffix == ".md":
                agent_file = item
            elif item.is_dir() and (item / "agent.md").is_file():
                agent_file = item / "agent.md"
                agent_id = item.name

            if agent_file and agent_id not in seen:
                seen.add(agent_id)
                meta: Dict[str, Any] = {}
                try:
                    text = agent_file.read_text(encoding="utf-8")
                    if text.startswith("---"):
                        parts = text.split("---", 2)
                        if len(parts) >= 3:
                            meta = yaml.safe_load(parts[1]) or {}
                except Exception:
                    pass

                agents.append({
                    "id": agent_id,
                    "name": meta.get("name", agent_id),
                    "description": meta.get("description", ""),
                    "model": meta.get("model", "inherit"),
                    "path": str(agent_file),
                    "tools": meta.get("tools", {}),
                })
    return agents


def compile_agy_agent(
    definition: CanonicalAgentDefinition,
    config_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> Dict[str, Any]:
    agent_id = definition.id
    target_dirs = []
    if workspace_root:
        target_dirs.append(workspace_root / ".agents" / "agents" / agent_id)
    cfg = config_dir or get_agy_config_dir()
    target_dirs.append(cfg / "agents" / agent_id)

    frontmatter = {
        "name": definition.id,
        "description": definition.description or definition.name,
        "model": definition.preferences.model,
        "effort": definition.preferences.reasoning_effort,
        "tools": {
            "allowed": definition.capabilities.tools.allowed,
            "denied": definition.capabilities.tools.denied,
        },
        "skills": definition.capabilities.skills,
    }

    body = (
        f"# {definition.name}\n\n"
        f"## Persona\n{definition.identity.persona or definition.identity.role}\n\n"
        f"## Objectives\n{definition.identity.objective}\n\n"
        f"## Guidelines & Behavioral Rules\n"
        f"- Response style: {definition.preferences.response_style}\n"
        f"- Security: {definition.permissions.filesystem} filesystem, {definition.permissions.shell_execution} shell execution\n"
    )

    content = f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n{body}\n"

    last_md = None
    for target_dir in target_dirs:
        target_dir.mkdir(parents=True, exist_ok=True)
        agent_md = target_dir / "agent.md"
        agent_md.write_text(content, encoding="utf-8")
        last_md = agent_md

    return {
        "id": agent_id,
        "name": definition.name,
        "path": str(last_md),
        "status": "deployed",
    }


def delete_agy_agent(
    agent_id: str,
    config_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> bool:
    deleted = False
    candidates = []
    if workspace_root:
        candidates.append(workspace_root / ".agents" / "agents" / agent_id)
        candidates.append(workspace_root / ".agents" / "agents" / f"{agent_id}.md")
    cfg = config_dir or get_agy_config_dir()
    candidates.append(cfg / "agents" / agent_id)
    candidates.append(cfg / "agents" / f"{agent_id}.md")

    for c in candidates:
        if c.is_dir():
            shutil.rmtree(c, ignore_errors=True)
            deleted = True
        elif c.is_file():
            c.unlink(missing_ok=True)
            deleted = True
    return deleted
