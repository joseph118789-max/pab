"""Claude Code subagent compilation and inventory (Markdown + Frontmatter)."""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pab.core.models.agent import CanonicalAgentDefinition
from pab.providers.claude.config import get_claude_home


def list_claude_agents(home_dir: Optional[Path] = None, workspace_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    home = home_dir or get_claude_home()
    agents = []
    dirs_to_check = [home / "agents"]
    if workspace_root:
        dirs_to_check.append(workspace_root / ".claude" / "agents")

    seen = set()
    for directory in dirs_to_check:
        if not directory.is_dir():
            continue
        for md_file in directory.glob("*.md"):
            agent_id = md_file.stem
            if agent_id not in seen:
                seen.add(agent_id)
                meta: Dict[str, Any] = {}
                try:
                    text = md_file.read_text(encoding="utf-8")
                    if text.startswith("---"):
                        parts = text.split("---", 2)
                        if len(parts) >= 3:
                            front = yaml.safe_load(parts[1]) or {}
                            meta = {
                                "id": front.get("name", agent_id),
                                "name": front.get("name", agent_id),
                                "description": front.get("description", ""),
                                "tools": front.get("tools", []),
                                "path": str(md_file),
                            }
                except Exception:
                    meta = {"id": agent_id, "name": agent_id, "path": str(md_file)}
                agents.append(meta)
    return agents


def compile_claude_agent(
    definition: CanonicalAgentDefinition,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> Dict[str, Any]:
    home = home_dir or get_claude_home()
    if workspace_root:
        target_dir = workspace_root / ".claude" / "agents"
    else:
        target_dir = home / "agents"

    target_dir.mkdir(parents=True, exist_ok=True)
    md_path = target_dir / f"{definition.id}.md"

    # Map tools to Claude tool conventions (Read, Edit, Bash, etc.)
    claude_tools = []
    tool_map = {
        "read": "Read",
        "search": "Grep",
        "terminal": "Bash",
        "file_edit": "Edit",
    }
    for t in definition.capabilities.tools.allowed:
        claude_tools.append(tool_map.get(t.lower(), t.capitalize()))

    frontmatter = {
        "name": definition.id,
        "description": definition.description or definition.name,
        "tools": claude_tools,
    }

    body = (
        f"# {definition.name}\n\n"
        f"You are {definition.name}. Role: {definition.identity.role}.\n\n"
        f"## Persona\n{definition.identity.persona}\n\n"
        f"## Objective\n{definition.identity.objective}\n\n"
        f"## Operating Guidelines\n"
        f"- Style: {definition.preferences.response_style}\n"
        f"- Never execute commands without verifying files and parameters.\n"
    )

    content = f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n{body}\n"
    md_path.write_text(content, encoding="utf-8")

    return {
        "id": definition.id,
        "name": definition.name,
        "path": str(md_path),
        "status": "deployed",
    }


def delete_claude_agent(
    agent_id: str,
    home_dir: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
) -> bool:
    home = home_dir or get_claude_home()
    deleted = False
    candidates = []
    if workspace_root:
        candidates.append(workspace_root / ".claude" / "agents" / f"{agent_id}.md")
    candidates.append(home / "agents" / f"{agent_id}.md")

    for c in candidates:
        if c.is_file():
            c.unlink(missing_ok=True)
            deleted = True
    return deleted
