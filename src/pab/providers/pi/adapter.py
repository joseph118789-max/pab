"""Pi Coding Agent Provider Adapter."""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.agent import CanonicalAgentDefinition
from pab.core.models.session import NormalizedSession
from pab.core.models.skill import CanonicalSkill
from pab.providers.base import AgentProvider
from pab.providers.pi.agents import (
    compile_pi_agent,
    delete_pi_agent,
    list_pi_agents,
)
from pab.providers.pi.config import (
    get_pi_bin,
    get_pi_home,
)
from pab.providers.pi.memory import list_pi_memories
from pab.providers.pi.sessions import (
    export_pi_session,
    list_pi_sessions,
)
from pab.providers.pi.skills import (
    install_pi_skill,
    list_pi_skills,
    remove_pi_skill,
)


class PiAdapter(AgentProvider):
    """Adapter for Pi Coding Agent platform."""

    def __init__(
        self,
        home_dir: Optional[Path] = None,
        workspace_root: Optional[Path] = None,
    ):
        self._home = home_dir or get_pi_home()
        self._workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "pi"

    @property
    def display_name(self) -> str:
        return "Pi Coding Agent"

    def detect(self) -> bool:
        return bool(get_pi_bin() or self._home.is_dir())

    def version(self) -> Optional[str]:
        bin_path = get_pi_bin()
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
            "instruction_files": ["AGENTS.md", "CLAUDE.md"],
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        return list_pi_agents(self._home, self._workspace_root)

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        for a in self.list_agents():
            if a["id"] == agent_id:
                return a
        return None

    def create_agent(self, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_pi_agent(definition, self._home, self._workspace_root)

    def update_agent(self, agent_id: str, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_pi_agent(definition, self._home, self._workspace_root)

    def delete_agent(self, agent_id: str) -> bool:
        return delete_pi_agent(agent_id, self._home, self._workspace_root)

    def list_skills(self) -> List[Dict[str, Any]]:
        return list_pi_skills(self._home, self._workspace_root)

    def install_skill(self, skill: CanonicalSkill) -> bool:
        return install_pi_skill(skill, self._home, self._workspace_root)

    def remove_skill(self, skill_id: str) -> bool:
        return remove_pi_skill(skill_id, self._home, self._workspace_root)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return list_pi_sessions(self._home)

    def export_session(self, session_id: str) -> Optional[NormalizedSession]:
        return export_pi_session(session_id, self._home)

    def resume_session(self, session_id: str) -> bool:
        return False

    def validate(self, definition: CanonicalAgentDefinition) -> List[str]:
        return []

    def export_canonical_agent(self, agent_id: str) -> Optional[CanonicalAgentDefinition]:
        return None
