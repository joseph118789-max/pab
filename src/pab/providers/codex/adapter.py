"""OpenAI Codex CLI Provider Adapter."""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.agent import CanonicalAgentDefinition
from pab.core.models.session import NormalizedSession
from pab.core.models.skill import CanonicalSkill
from pab.providers.base import AgentAdapter, AgentProvider
from pab.providers.codex.agents import (
    compile_codex_agent,
    delete_codex_agent,
    list_codex_agents,
)
from pab.providers.codex.config import (
    get_codex_bin,
    get_codex_home,
)
from pab.providers.codex.memory import list_codex_memories
from pab.providers.codex.sessions import (
    export_codex_session,
    list_codex_sessions,
)
from pab.providers.codex.skills import (
    install_codex_skill,
    list_codex_skills,
    remove_codex_skill,
)


class CodexAdapter(AgentAdapter):
    """Adapter for OpenAI Codex CLI platform."""

    def __init__(self, home_dir: Optional[Path] = None, workspace_root: Optional[Path] = None):
        self._home = home_dir or get_codex_home()
        self._workspace_root = workspace_root

    def get_executable_path(self) -> Optional[str]:
        return get_codex_bin()

    def supported_operations(self) -> List[str]:
        return [
            "discover",
            "capabilities",
            "list_agents",
            "get_agent",
            "create_agent",
            "update_agent",
            "delete_agent",
            "list_skills",
            "install_skill",
            "remove_skill",
            "list_sessions",
            "export_session",
            "resume",
            "launch",
            "stop",
            "inspect",
        ]

    @property
    def name(self) -> str:
        return "codex"

    @property
    def display_name(self) -> str:
        return "OpenAI Codex CLI"

    def detect(self) -> bool:
        return bool(get_codex_bin() or self._home.is_dir())

    def version(self) -> Optional[str]:
        bin_path = get_codex_bin()
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
            "agent_management": True,
            "toml_custom_agents": True,
            "skills": True,
            "system_skills": True,
            "memory": True,
            "sessions": True,
            "native_resume": True,
            "instruction_files": ["AGENTS.md", ".codex/instructions.md"],
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        return list_codex_agents(self._home, self._workspace_root)

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        for a in self.list_agents():
            if a["id"] == agent_id:
                return a
        return None

    def create_agent(self, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_codex_agent(definition, self._home, self._workspace_root)

    def update_agent(self, agent_id: str, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_codex_agent(definition, self._home, self._workspace_root)

    def delete_agent(self, agent_id: str) -> bool:
        return delete_codex_agent(agent_id, self._home, self._workspace_root)

    def list_skills(self) -> List[Dict[str, Any]]:
        return list_codex_skills(self._home, self._workspace_root)

    def install_skill(self, skill: CanonicalSkill) -> bool:
        return install_codex_skill(skill, self._home, self._workspace_root)

    def remove_skill(self, skill_id: str) -> bool:
        return remove_codex_skill(skill_id, self._home, self._workspace_root)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return list_codex_sessions(self._home)

    def export_session(self, session_id: str) -> Optional[NormalizedSession]:
        return export_codex_session(session_id, self._home)

    def resume_session(self, session_id: str) -> bool:
        bin_path = get_codex_bin()
        if not bin_path:
            return False
        return True

    def validate(self, definition: CanonicalAgentDefinition) -> List[str]:
        warnings = []
        if definition.identity.avatar_emoji != "🤖":
            warnings.append("Codex custom agent TOML does not have an avatar_emoji field; will be omitted.")
        return warnings

    def export_canonical_agent(self, agent_id: str) -> Optional[CanonicalAgentDefinition]:
        ag = self.get_agent(agent_id)
        if not ag or not ag.get("path"):
            return None
        from pab.core.models.agent import AgentIdentity, AgentInstructions
        return CanonicalAgentDefinition(
            id=agent_id,
            name=ag.get("name", agent_id),
            description=ag.get("description", ""),
            identity=AgentIdentity(role=ag.get("name", agent_id)),
            instructions=AgentInstructions(),
        )
