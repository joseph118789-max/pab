"""Anthropic Claude Code Provider Adapter."""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.agent import CanonicalAgentDefinition
from pab.core.models.session import NormalizedSession
from pab.core.models.skill import CanonicalSkill
from pab.providers.base import AgentProvider
from pab.providers.claude.agents import (
    compile_claude_agent,
    delete_claude_agent,
    list_claude_agents,
)
from pab.providers.claude.config import (
    get_claude_bin,
    get_claude_home,
)
from pab.providers.claude.memory import list_claude_memories
from pab.providers.claude.sessions import (
    export_claude_session,
    list_claude_sessions,
)
from pab.providers.claude.skills import (
    install_claude_skill,
    list_claude_skills,
    remove_claude_skill,
)


class ClaudeAdapter(AgentProvider):
    """Adapter for Anthropic Claude Code platform."""

    def __init__(self, home_dir: Optional[Path] = None, workspace_root: Optional[Path] = None):
        self._home = home_dir or get_claude_home()
        self._workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "claude"

    @property
    def display_name(self) -> str:
        return "Anthropic Claude Code"

    def detect(self) -> bool:
        return bool(get_claude_bin() or self._home.is_dir())

    def version(self) -> Optional[str]:
        bin_path = get_claude_bin()
        if bin_path:
            try:
                proc = subprocess.run(
                    [bin_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if proc.returncode == 0:
                    return proc.stdout.strip()
            except Exception:
                pass
        return None

    def capabilities(self) -> Dict[str, Any]:
        return {
            "subagents": True,
            "markdown_agents": True,
            "skills": True,
            "memory": True,
            "sessions": True,
            "native_resume": True,
            "instruction_files": ["CLAUDE.md", "AGENTS.md"],
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        return list_claude_agents(self._home, self._workspace_root)

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        for a in self.list_agents():
            if a["id"] == agent_id:
                return a
        return None

    def create_agent(self, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_claude_agent(definition, self._home, self._workspace_root)

    def update_agent(self, agent_id: str, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_claude_agent(definition, self._home, self._workspace_root)

    def delete_agent(self, agent_id: str) -> bool:
        return delete_claude_agent(agent_id, self._home, self._workspace_root)

    def list_skills(self) -> List[Dict[str, Any]]:
        return list_claude_skills(self._home, self._workspace_root)

    def install_skill(self, skill: CanonicalSkill) -> bool:
        return install_claude_skill(skill, self._home, self._workspace_root)

    def remove_skill(self, skill_id: str) -> bool:
        return remove_claude_skill(skill_id, self._home, self._workspace_root)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return list_claude_sessions(self._home)

    def export_session(self, session_id: str) -> Optional[NormalizedSession]:
        return export_claude_session(session_id, self._home)

    def resume_session(self, session_id: str) -> bool:
        bin_path = get_claude_bin()
        if not bin_path:
            return False
        return True

    def validate(self, definition: CanonicalAgentDefinition) -> List[str]:
        warnings = []
        if definition.preferences.reasoning_effort != "inherit":
            warnings.append(
                f"Claude Code subagents do not take a reasoning_effort parameter: '{definition.preferences.reasoning_effort}'"
            )
        return warnings
