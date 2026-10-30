"""Google Antigravity CLI (agy) Provider Adapter."""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.agent import CanonicalAgentDefinition
from pab.core.models.session import NormalizedSession
from pab.core.models.skill import CanonicalSkill
from pab.providers.agy.agents import (
    compile_agy_agent,
    delete_agy_agent,
    list_agy_agents,
)
from pab.providers.agy.config import (
    get_agy_bin,
    get_agy_cli_dir,
    get_agy_config_dir,
)
from pab.providers.agy.memory import list_agy_memories
from pab.providers.agy.sessions import (
    export_agy_session,
    list_agy_sessions,
)
from pab.providers.agy.skills import (
    install_agy_skill,
    list_agy_skills,
    remove_agy_skill,
)
from pab.providers.base import AgentProvider


class AgyAdapter(AgentProvider):
    """Adapter for Google Antigravity CLI (agy)."""

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        cli_dir: Optional[Path] = None,
        workspace_root: Optional[Path] = None,
    ):
        self._config_dir = config_dir or get_agy_config_dir()
        self._cli_dir = cli_dir or get_agy_cli_dir()
        self._workspace_root = workspace_root

    @property
    def name(self) -> str:
        return "agy"

    @property
    def display_name(self) -> str:
        return "Google Antigravity CLI (agy)"

    def detect(self) -> bool:
        return bool(get_agy_bin() or self._config_dir.is_dir() or self._cli_dir.is_dir())

    def version(self) -> Optional[str]:
        bin_path = get_agy_bin()
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
            "progressive_disclosure_skills": True,
            "skills": True,
            "rules": True,
            "sessions": True,
            "native_resume": True,
            "instruction_files": ["GEMINI.md", "AGENTS.md", "agent.md"],
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        return list_agy_agents(self._config_dir, self._workspace_root)

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        for a in self.list_agents():
            if a["id"] == agent_id:
                return a
        return None

    def create_agent(self, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_agy_agent(definition, self._config_dir, self._workspace_root)

    def update_agent(self, agent_id: str, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_agy_agent(definition, self._config_dir, self._workspace_root)

    def delete_agent(self, agent_id: str) -> bool:
        return delete_agy_agent(agent_id, self._config_dir, self._workspace_root)

    def list_skills(self) -> List[Dict[str, Any]]:
        return list_agy_skills(self._config_dir, self._workspace_root)

    def install_skill(self, skill: CanonicalSkill) -> bool:
        return install_agy_skill(skill, self._config_dir, self._workspace_root)

    def remove_skill(self, skill_id: str) -> bool:
        return remove_agy_skill(skill_id, self._config_dir, self._workspace_root)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return list_agy_sessions(self._cli_dir)

    def export_session(self, session_id: str) -> Optional[NormalizedSession]:
        return export_agy_session(session_id, self._cli_dir)

    def resume_session(self, session_id: str) -> bool:
        bin_path = get_agy_bin()
        if not bin_path:
            return False
        # Native resume via agy --conversation
        return True

    def validate(self, definition: CanonicalAgentDefinition) -> List[str]:
        warnings = []
        if definition.preferences.reasoning_effort not in ["inherit", "low", "medium", "high", "xhigh", "max"]:
            warnings.append(
                f"Antigravity CLI expects effort to be low|medium|high|xhigh|max. Found: '{definition.preferences.reasoning_effort}'"
            )
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
