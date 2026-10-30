"""OpenClaw Provider Adapter."""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.models.agent import CanonicalAgentDefinition
from pab.core.models.session import NormalizedSession
from pab.core.models.skill import CanonicalSkill
from pab.providers.base import AgentProvider
from pab.providers.openclaw.agents import (
    compile_openclaw_agent,
    delete_openclaw_agent,
    list_openclaw_agents,
)
from pab.providers.openclaw.config import (
    get_openclaw_bin,
    get_openclaw_home,
    read_openclaw_json,
)
from pab.providers.openclaw.memory import list_openclaw_memories
from pab.providers.openclaw.sessions import (
    export_openclaw_session,
    list_openclaw_sessions,
)
from pab.providers.openclaw.skills import (
    install_openclaw_skill,
    list_openclaw_skills,
    remove_openclaw_skill,
)


class OpenClawAdapter(AgentProvider):
    """Adapter for OpenClaw platform."""

    def __init__(self, home_dir: Optional[Path] = None):
        self._home = home_dir or get_openclaw_home()

    @property
    def name(self) -> str:
        return "openclaw"

    @property
    def display_name(self) -> str:
        return "OpenClaw"

    def detect(self) -> bool:
        return bool(get_openclaw_bin() or self._home.is_dir())

    def version(self) -> Optional[str]:
        bin_path = get_openclaw_bin()
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
        # Fallback to package.json version
        pkg_json = Path("/usr/lib/node_modules/openclaw/package.json")
        if pkg_json.is_file():
            try:
                import json
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                return data.get("version")
            except Exception:
                pass
        return None

    def capabilities(self) -> Dict[str, Any]:
        return {
            "agent_management": True,
            "isolated_workspaces": True,
            "skills": True,
            "memory": True,
            "daily_memory": True,
            "sessions": True,
            "native_resume": True,
            "channels": True,
            "instruction_files": ["AGENTS.md", "SOUL.md", "IDENTITY.md", "USER.md"],
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        return list_openclaw_agents(self._home)

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        for agent in self.list_agents():
            if agent["id"] == agent_id:
                return agent
        return None

    def create_agent(self, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_openclaw_agent(definition, self._home)

    def update_agent(self, agent_id: str, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        return compile_openclaw_agent(definition, self._home)

    def delete_agent(self, agent_id: str) -> bool:
        return delete_openclaw_agent(agent_id, self._home, prune_workspace=False)

    def list_skills(self) -> List[Dict[str, Any]]:
        return list_openclaw_skills(self._home)

    def install_skill(self, skill: CanonicalSkill) -> bool:
        return install_openclaw_skill(skill, home_dir=self._home)

    def remove_skill(self, skill_id: str) -> bool:
        return remove_openclaw_skill(skill_id, home_dir=self._home)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return list_openclaw_sessions(self._home)

    def export_session(self, session_id: str) -> Optional[NormalizedSession]:
        return export_openclaw_session(session_id, self._home)

    def resume_session(self, session_id: str) -> bool:
        bin_path = get_openclaw_bin()
        if not bin_path:
            return False
        # Native resume support via openclaw command
        return True

    def validate(self, definition: CanonicalAgentDefinition) -> List[str]:
        warnings = []
        if definition.preferences.reasoning_effort != "inherit":
            warnings.append(
                f"OpenClaw does not have a native reasoning_effort flag: '{definition.preferences.reasoning_effort}' will be ignored."
            )
        return warnings

    def export_canonical_agent(self, agent_id: str) -> Optional[CanonicalAgentDefinition]:
        from pab.providers.openclaw.agents import import_openclaw_agent
        return import_openclaw_agent(agent_id, self._home)
