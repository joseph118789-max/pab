"""MiniMax Coding CLI (mcode) Provider Adapter."""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.agent import CanonicalAgentDefinition
from pab.core.models.session import NormalizedSession
from pab.core.models.skill import CanonicalSkill
from pab.providers.base import AgentAdapter, AgentProvider
from pab.providers.minimax.agents import (
    compile_minimax_agent,
    delete_minimax_agent,
    list_minimax_agents,
)
from pab.providers.minimax.config import (
    get_minimax_bin,
    get_minimax_home,
)
from pab.providers.minimax.skills import (
    install_minimax_skill,
    list_minimax_skills,
    remove_minimax_skill,
)


class MinimaxAdapter(AgentAdapter):
    """Adapter for MiniMax Coding (mcode) platform."""

    def __init__(
        self,
        home_dir: Optional[Path] = None,
        workspace_root: Optional[Path] = None,
    ):
        self._home = home_dir or get_minimax_home()
        self._workspace_root = workspace_root

    def get_executable_path(self) -> Optional[str]:
        return get_minimax_bin() or "/usr/bin/mcode"

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
        return "minimax"

    @property
    def display_name(self) -> str:
        return "MiniMax Coding (mcode)"

    def detect(self) -> bool:
        return bool(get_minimax_bin() or self._home.is_dir())

    def version(self) -> Optional[str]:
        bin_path = get_minimax_bin()
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
            "markdown_agents": True,
            "skills": True,
            "memory": True,
            "sessions": True,
            "native_resume": True,
            "instruction_files": ["AGENTS.md", "agent.md"],
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        return list_minimax_agents(self._home, self._workspace_root)

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        for a in self.list_agents():
            if a["id"] == agent_id:
                return a
        return None

    def create_agent(self, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_minimax_agent(definition, self._home, self._workspace_root)

    def update_agent(self, agent_id: str, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_minimax_agent(definition, self._home, self._workspace_root)

    def delete_agent(self, agent_id: str) -> bool:
        return delete_minimax_agent(agent_id, self._home, self._workspace_root)

    def list_skills(self) -> List[Dict[str, Any]]:
        return list_minimax_skills(self._home, self._workspace_root)

    def install_skill(self, skill: CanonicalSkill) -> bool:
        return install_minimax_skill(skill, self._home, self._workspace_root)

    def remove_skill(self, skill_id: str) -> bool:
        return remove_minimax_skill(skill_id, self._home, self._workspace_root)

    def list_sessions(self) -> List[Dict[str, Any]]:
        sessions_dir = self._home / "sessions"
        results = []
        if sessions_dir.is_dir():
            for item in sessions_dir.iterdir():
                results.append({"id": item.stem, "path": str(item)})
        return results

    def export_session(self, session_id: str) -> Optional[NormalizedSession]:
        return None

    def resume_session(self, session_id: str) -> bool:
        return False

    def validate(self, definition: CanonicalAgentDefinition) -> List[str]:
        return []

    def export_canonical_agent(self, agent_id: str) -> Optional[CanonicalAgentDefinition]:
        return None
