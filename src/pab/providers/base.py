"""Abstract Base Provider interface for AI Agent platforms."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pab.core.models.agent import CanonicalAgentDefinition
from pab.core.models.session import NormalizedSession
from pab.core.models.skill import CanonicalSkill


class AgentProvider(ABC):
    """Abstract interface representing an external agent runtime/CLI provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. openclaw, agy, codex, claude)."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable provider name."""
        pass

    @abstractmethod
    def detect(self) -> bool:
        """Return True if provider CLI/environment is available on the machine."""
        pass

    @abstractmethod
    def version(self) -> Optional[str]:
        """Return installed version string or None."""
        pass

    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities dictionary."""
        pass

    @abstractmethod
    def list_agents(self) -> List[Dict[str, Any]]:
        """List currently configured native agents."""
        pass

    @abstractmethod
    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve native agent details if configured."""
        pass

    @abstractmethod
    def create_agent(self, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        """Compile and deploy a canonical agent into the provider's native format."""
        pass

    @abstractmethod
    def update_agent(self, agent_id: str, definition: CanonicalAgentDefinition) -> Dict[str, Any]:
        """Update existing native agent configuration."""
        pass

    @abstractmethod
    def delete_agent(self, agent_id: str) -> bool:
        """Remove native agent configuration and prune if appropriate."""
        pass

    @abstractmethod
    def list_skills(self) -> List[Dict[str, Any]]:
        """List skills available in this provider."""
        pass

    @abstractmethod
    def install_skill(self, skill: CanonicalSkill) -> bool:
        """Deploy a canonical skill into the provider's skill repository."""
        pass

    @abstractmethod
    def remove_skill(self, skill_id: str) -> bool:
        """Remove a skill from the provider."""
        pass

    @abstractmethod
    def list_sessions(self) -> List[Dict[str, Any]]:
        """Discover sessions managed by this provider."""
        pass

    @abstractmethod
    def export_session(self, session_id: str) -> Optional[NormalizedSession]:
        """Export and normalize a native session."""
        pass

    @abstractmethod
    def resume_session(self, session_id: str) -> bool:
        """Trigger native resume for this provider if supported."""
        pass

    @abstractmethod
    def validate(self, definition: CanonicalAgentDefinition) -> List[str]:
        """Validate whether provider supports all specified agent fields. Returns warnings."""
        pass
