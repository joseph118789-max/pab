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
                    name = data.get("name") or agent_sec.get("name", agent_id)
                    description = data.get("description") or agent_sec.get("description", "")
                    model = data.get("model") or agent_sec.get("model", "inherit")
                    meta = {
                        "id": agent_id,
                        "name": str(name),
                        "description": str(description),
                        "model": str(model),
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
    doc.add("name", definition.name)
    doc.add("description", definition.description or definition.name)

    instructions_parts = [
        f"You are {definition.name}. Role: {definition.identity.role}.",
        f"Objective: {definition.identity.objective}",
    ]
    if definition.capabilities.tools.allowed:
        instructions_parts.append(f"Allowed Tools: {', '.join(definition.capabilities.tools.allowed)}")
    if definition.capabilities.tools.denied:
        instructions_parts.append(f"Denied Tools: {', '.join(definition.capabilities.tools.denied)}")
    if definition.capabilities.skills:
        instructions_parts.append(f"Assigned Skills: {', '.join(definition.capabilities.skills)}")
    developer_instructions = "\n".join(instructions_parts) + "\n"

    doc.add("developer_instructions", developer_instructions)

    if definition.preferences.model and definition.preferences.model != "inherit":
        doc.add("model", definition.preferences.model)
    if definition.preferences.reasoning_effort and definition.preferences.reasoning_effort != "inherit":
        doc.add("model_reasoning_effort", definition.preferences.reasoning_effort)

    nicknames = [definition.id]
    candidate = definition.name.lower().replace(" ", "-")
    if candidate not in nicknames:
        nicknames.append(candidate)
    doc.add("nickname_candidates", nicknames)

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
