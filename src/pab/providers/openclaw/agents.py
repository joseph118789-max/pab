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


def import_openclaw_agent(
    agent_id: str,
    home_dir: Optional[Path] = None,
) -> Optional[CanonicalAgentDefinition]:
    """Import an existing OpenClaw agent and convert it into a CanonicalAgentDefinition."""
    from pab.core.models.agent import (
        AgentCapabilities,
        AgentIdentity,
        AgentInstructions,
        AgentPermissions,
        AgentPreferences,
        AgentToolCapabilities,
        ProviderConfig,
    )

    home = home_dir or get_openclaw_home()
    cfg = read_openclaw_json(home / "openclaw.json")
    entries = cfg.get("agents", {}).get("entries", {})
    entry = entries.get(agent_id, {})

    # Determine workspace directory
    workspace_path = None
    if entry.get("workspace"):
        workspace_path = Path(entry["workspace"]).expanduser().resolve()
    elif agent_id == "main":
        workspace_path = (home / "workspace").resolve()
    elif (home / "agents" / agent_id).is_dir():
        workspace_path = (home / "agents" / agent_id).resolve()

    if not workspace_path or not workspace_path.is_dir():
        return None

    # Read workspace identity files
    identity_file = workspace_path / "IDENTITY.md"
    soul_file = workspace_path / "SOUL.md"
    user_file = workspace_path / "USER.md"
    agents_file = workspace_path / "AGENTS.md"

    name = entry.get("name")
    avatar_emoji = entry.get("identity", {}).get("emoji", "🦞")
    role = "General Assistant & Coordinator"
    persona = ""
    vibe = "Resourceful, opinionated, genuinely helpful"

    if identity_file.is_file():
        id_text = identity_file.read_text(encoding="utf-8")
        import re
        for line in id_text.splitlines():
            line_str = line.strip()
            m_name = re.search(r"-\s*\*\*Name:\*\*\s*(.*)", line_str)
            if m_name and m_name.group(1).strip().strip("_()"):
                name = m_name.group(1).strip().strip("_()")
            m_emoji = re.search(r"-\s*\*\*Emoji:\*\*\s*(.*)", line_str)
            if m_emoji and m_emoji.group(1).strip().strip("_()"):
                avatar_emoji = m_emoji.group(1).strip().strip("_()")
            m_creature = re.search(r"-\s*\*\*Creature:\*\*\s*(.*)", line_str)
            if m_creature and m_creature.group(1).strip().strip("_()"):
                role = m_creature.group(1).strip().strip("_()")
            m_vibe = re.search(r"-\s*\*\*Vibe:\*\*\s*(.*)", line_str)
            if m_vibe and m_vibe.group(1).strip().strip("_()"):
                vibe = m_vibe.group(1).strip().strip("_()")

    soul_text = ""
    if soul_file.is_file():
        soul_text = soul_file.read_text(encoding="utf-8")
        persona = soul_text[:300].strip()

    agents_text = ""
    if agents_file.is_file():
        agents_text = agents_file.read_text(encoding="utf-8")

    # Discover skills in workspace
    skills = list(entry.get("skills", []))
    ws_skills_dir = workspace_path / "skills"
    if ws_skills_dir.is_dir():
        for sd in ws_skills_dir.iterdir():
            if sd.is_dir() and (sd / "SKILL.md").is_file() and sd.name not in skills and not sd.name.startswith("."):
                skills.append(sd.name)

    model = entry.get("model") or cfg.get("models", {}).get("default") or "minimax-portal/MiniMax-M2.7"
    display_name = name or ("OpenClaw Main" if agent_id == "main" else agent_id.capitalize())

    definition = CanonicalAgentDefinition(
        id=agent_id,
        name=display_name,
        description=f"Imported OpenClaw {agent_id} agent from workspace {workspace_path}",
        version="1.0.0",
        identity=AgentIdentity(
            role=role,
            persona=persona or f"OpenClaw {agent_id} agent",
            objective=f"Autonomous assistance and workspace management for OpenClaw {agent_id}",
            avatar_emoji=avatar_emoji,
            style=vibe,
        ),
        instructions=AgentInstructions(
            system_prompt=agents_text or f"You are {display_name}, managing {workspace_path}",
            soul_prompt=soul_text if soul_file.is_file() else None,
            user_prompt=user_file.read_text(encoding="utf-8") if user_file.is_file() else None,
        ),
        capabilities=AgentCapabilities(
            skills=skills,
            tools=AgentToolCapabilities(allowed=["read", "search", "terminal", "file_edit"]),
        ),
        preferences=AgentPreferences(
            model=model,
            response_style="technical",
        ),
        permissions=AgentPermissions(
            filesystem="workspace",
            shell_execution="approval_required",
            network="restricted",
        ),
        providers={
            "openclaw": ProviderConfig(
                enabled=True,
                workspace=str(workspace_path),
                model=model,
            )
        },
        metadata={
            "imported_from": "openclaw",
            "original_workspace": str(workspace_path),
        },
    )
    return definition
