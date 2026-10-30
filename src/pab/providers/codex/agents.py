"""OpenAI Codex agent definition compilation and inventory (TOML)."""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import tomlkit
from pab.core.models.agent import CanonicalAgentDefinition
from pab.providers.codex.config import get_codex_home


def list_codex_agents(home_dir: Optional[Path] = None, workspace_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    home = home_dir or get_codex_home()
    agents = []
    dirs_to_check = [home / "agents"]
    if workspace_root:
        dirs_to_check.append(workspace_root / ".codex" / "agents")

    seen = set()
    for directory in dirs_to_check:
        if not directory.is_dir():
            continue
        for toml_file in directory.glob("*.toml"):
            agent_id = toml_file.stem
            if agent_id not in seen:
                seen.add(agent_id)
                meta: Dict[str, Any] = {}
                try:
                    text = toml_file.read_text(encoding="utf-8")
                    data = tomlkit.parse(text)
                    agent_sec = data.get("agent", {})
                    meta = {
                        "id": agent_sec.get("id", agent_id),
                        "name": agent_sec.get("name", agent_id),
                        "description": agent_sec.get("description", ""),
                        "model": agent_sec.get("model", "inherit"),
                        "path": str(toml_file),
                    }
                except Exception:
                    meta = {"id": agent_id, "name": agent_id, "path": str(toml_file)}
                agents.append(meta)
    return agents


def compile_codex_agent(
    definition: CanonicalAgentDefinition,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> Dict[str, Any]:
    home = home_dir or get_codex_home()
    if workspace_root:
        target_dir = workspace_root / ".codex" / "agents"
    else:
        target_dir = home / "agents"

    target_dir.mkdir(parents=True, exist_ok=True)
    toml_path = target_dir / f"{definition.id}.toml"

    doc = tomlkit.document()
    agent_table = tomlkit.table()
    agent_table.add("id", definition.id)
    agent_table.add("name", definition.name)
    agent_table.add("description", definition.description or definition.name)
    agent_table.add("version", definition.version)
    agent_table.add("model", definition.preferences.model)
    agent_table.add("reasoning_effort", definition.preferences.reasoning_effort)
    doc.add("agent", agent_table)

    inst_table = tomlkit.table()
    instructions_text = (
        f"You are {definition.name}. Role: {definition.identity.role}.\n"
        f"Objective: {definition.identity.objective}\n"
    )
    inst_table.add("system_prompt", instructions_text)
    doc.add("instructions", inst_table)

    tools_table = tomlkit.table()
    tools_table.add("allowed", definition.capabilities.tools.allowed)
    tools_table.add("denied", definition.capabilities.tools.denied)
    doc.add("tools", tools_table)

    skills_table = tomlkit.table()
    skills_table.add("include", definition.capabilities.skills)
    doc.add("skills", skills_table)

    toml_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    return {
        "id": definition.id,
        "name": definition.name,
        "path": str(toml_path),
        "status": "deployed",
    }


def delete_codex_agent(
    agent_id: str,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> bool:
    home = home_dir or get_codex_home()
    deleted = False
    candidates = []
    if workspace_root:
        candidates.append(workspace_root / ".codex" / "agents" / f"{agent_id}.toml")
    candidates.append(home / "agents" / f"{agent_id}.toml")

    for c in candidates:
        if c.is_file():
            c.unlink(missing_ok=True)
            deleted = True
    return deleted
