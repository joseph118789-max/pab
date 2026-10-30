"""OpenClaw agent compilation, workspace generation, and inventory."""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.agent import CanonicalAgentDefinition
from pab.providers.openclaw.config import (
    get_openclaw_home,
    read_openclaw_json,
    write_openclaw_json,
)


def list_openclaw_agents(home_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    home = home_dir or get_openclaw_home()
    config = read_openclaw_json(home / "openclaw.json")
    entries = config.get("agents", {}).get("entries", {})
    results = []

    # Read configured entries
    if isinstance(entries, dict):
        for agent_id, data in entries.items():
            results.append({
                "id": agent_id,
                "name": data.get("name", agent_id),
                "workspace": data.get("workspace"),
                "model": data.get("model"),
                "skills": data.get("skills", []),
                "identity": data.get("identity", {}),
            })

    # Read directories in ~/.openclaw/agents
    agents_dir = home / "agents"
    if agents_dir.is_dir():
        for d in agents_dir.iterdir():
            if d.is_dir() and not any(r["id"] == d.name for r in results):
                identity_file = d / "IDENTITY.md"
                identity_text = identity_file.read_text("utf-8") if identity_file.is_file() else ""
                results.append({
                    "id": d.name,
                    "name": d.name.capitalize(),
                    "workspace": str(d),
                    "model": "minimax-portal/MiniMax-M2.7",
                    "skills": [],
                    "identity": {"name": d.name, "snippet": identity_text[:100]},
                })
    return results


def compile_openclaw_agent(
    definition: CanonicalAgentDefinition,
    home_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    home = home_dir or get_openclaw_home()
    agent_id = definition.id
    prov_cfg = definition.providers.get("openclaw")

    # Workspace directory
    workspace_path = (
        Path(prov_cfg.workspace).expanduser().resolve()
        if (prov_cfg and prov_cfg.workspace)
        else (home / "agents" / agent_id).resolve()
    )
    agent_dir = workspace_path / "agent"
    workspace_path.mkdir(parents=True, exist_ok=True)
    agent_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate IDENTITY.md
    identity_md = workspace_path / "IDENTITY.md"
    identity_content = (
        f"# {definition.name}\n\n"
        f"- Role: {definition.identity.role}\n"
        f"- Persona: {definition.identity.persona or 'Specialist'}\n"
        f"- Objective: {definition.identity.objective}\n"
        f"- Emoji: {definition.identity.avatar_emoji}\n"
        f"- Tone: {definition.identity.style}\n"
    )
    identity_md.write_text(identity_content, encoding="utf-8")

    # 2. Generate SOUL.md
    soul_md = workspace_path / "SOUL.md"
    soul_content = (
        f"# {definition.name} Core Values & Principles\n\n"
        f"You are {definition.name}. You operate with the following principles:\n"
        f"- Always prioritize accuracy, safety, and operational reliability.\n"
        f"- Ask for confirmation before performing irreversible changes.\n"
        f"- Keep instructions aligned with the user's objective: {definition.identity.objective}\n"
    )
    soul_md.write_text(soul_content, encoding="utf-8")

    # 3. Generate USER.md
    user_md = workspace_path / "USER.md"
    user_content = (
        "# User Preferences\n\n"
        "- Response format: Markdown with concise technical explanations\n"
        "- Verify file paths before modifying\n"
    )
    user_md.write_text(user_content, encoding="utf-8")

    # 4. Generate AGENTS.md
    agents_md = workspace_path / "AGENTS.md"
    agents_content = (
        f"# Agent Guidelines for {definition.name}\n\n"
        f"## Scope & Objective\n{definition.identity.objective}\n\n"
        f"## Allowed Tools\n"
        + "\n".join(f"- `{t}`" for t in definition.capabilities.tools.allowed)
        + "\n\n"
        f"## Denied Tools\n"
        + "\n".join(f"- `{t}`" for t in definition.capabilities.tools.denied)
        + "\n"
    )
    agents_md.write_text(agents_content, encoding="utf-8")

    # 5. Generate MEMORY.md if not exists
    memory_md = workspace_path / "MEMORY.md"
    if not memory_md.exists():
        memory_md.write_text(f"# {definition.name} Curated Memory\n\n- Initialized via PAB\n", encoding="utf-8")

    # 6. Update openclaw.json entries
    config_file = home / "openclaw.json"
    cfg = read_openclaw_json(config_file)
    if "agents" not in cfg:
        cfg["agents"] = {"entries": {}, "defaults": {}}
    if "entries" not in cfg["agents"]:
        cfg["agents"]["entries"] = {}

    model_name = (
        (prov_cfg.model if prov_cfg and prov_cfg.model else None)
        or (definition.preferences.model if definition.preferences.model != "inherit" else "minimax-portal/MiniMax-M2.7")
    )
    tools_profile = (prov_cfg.tools_profile if prov_cfg and prov_cfg.tools_profile else "full")

    entry_data = {
        "name": definition.name,
        "workspace": str(workspace_path),
        "agentDir": str(agent_dir),
        "model": model_name,
        "skills": definition.capabilities.skills,
        "identity": {
            "name": definition.id,
            "emoji": definition.identity.avatar_emoji,
        },
        "tools": {
            "profile": tools_profile,
        },
    }
    cfg["agents"]["entries"][agent_id] = entry_data
    write_openclaw_json(cfg, config_file)

    return {
        "id": agent_id,
        "name": definition.name,
        "workspace": str(workspace_path),
        "status": "deployed",
    }


def delete_openclaw_agent(agent_id: str, home_dir: Optional[Path] = None, prune_workspace: bool = False) -> bool:
    home = home_dir or get_openclaw_home()
    config_file = home / "openclaw.json"
    cfg = read_openclaw_json(config_file)
    deleted = False

    if "agents" in cfg and "entries" in cfg["agents"] and agent_id in cfg["agents"]["entries"]:
        entry = cfg["agents"]["entries"].pop(agent_id)
        write_openclaw_json(cfg, config_file)
        deleted = True
        if prune_workspace and entry.get("workspace"):
            ws = Path(entry["workspace"])
            if ws.is_dir() and ws != home / "workspace":
                shutil.rmtree(ws, ignore_errors=True)

    agent_dir = home / "agents" / agent_id
    if prune_workspace and agent_dir.is_dir():
        shutil.rmtree(agent_dir, ignore_errors=True)
        deleted = True

    return deleted
