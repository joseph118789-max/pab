"""DeepSeek Shell (DSH) Provider Adapter."""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.agent import CanonicalAgentDefinition
from pab.core.models.session import NormalizedSession
from pab.core.models.skill import CanonicalSkill
from pab.providers.base import AgentProvider
from pab.providers.dsh.agents import (
    compile_dsh_agent,
    delete_dsh_agent,
    list_dsh_agents,
)
from pab.providers.dsh.config import (
    get_dsh_bin,
    get_dsh_home,
)
from pab.providers.dsh.memory import list_dsh_memories
from pab.providers.dsh.sessions import (
    export_dsh_session,
    list_dsh_sessions,
)
from pab.providers.dsh.skills import (
    install_dsh_skill,
    list_dsh_skills,
    remove_dsh_skill,
)


class DshAdapter(AgentProvider):
    """Adapter for DeepSeek Shell (DSH) platform."""

    def __init__(
        self,
        home_dir: Optional[Path] = None,
        workspace_root: Optional[Path] = None,
    ):
        self._home = home_dir or get_dsh_home()
        self._workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "dsh"

    @property
    def display_name(self) -> str:
        return "DeepSeek Shell (DSH)"

    def detect(self) -> bool:
        return bool(get_dsh_bin() or self._home.is_dir())

    def version(self) -> Optional[str]:
        bin_path = get_dsh_bin()
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
            "native_resume": False,
            "instruction_files": ["AGENTS.md", "DEEPSEEK.md"],
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        return list_dsh_agents(self._home, self._workspace_root)

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        for a in self.list_agents():
            if a["id"] == agent_id:
                return a
        return None

    def create_agent(self, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_dsh_agent(definition, self._home, self._workspace_root)

    def update_agent(self, agent_id: str, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_dsh_agent(definition, self._home, self._workspace_root)

    def delete_agent(self, agent_id: str) -> bool:
        return delete_dsh_agent(agent_id, self._home, self._workspace_root)

    def list_skills(self) -> List[Dict[str, Any]]:
        return list_dsh_skills(self._home, self._workspace_root)

    def install_skill(self, skill: CanonicalSkill) -> bool:
        return install_dsh_skill(skill, self._home, self._workspace_root)

    def remove_skill(self, skill_id: str) -> bool:
        return remove_dsh_skill(skill_id, self._home, self._workspace_root)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return list_dsh_sessions(self._home)

    def export_session(self, session_id: str) -> Optional[NormalizedSession]:
        return export_dsh_session(session_id, self._home)

    def resume_session(self, session_id: str) -> bool:
        return False

    def validate(self, definition: CanonicalAgentDefinition) -> List[str]:
        return []

    def export_canonical_agent(self, agent_id: str) -> Optional[CanonicalAgentDefinition]:
        return None
