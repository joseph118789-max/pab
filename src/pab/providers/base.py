"""Abstract Base Provider interface for AI Agent platforms."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional
from pab.core.exceptions import UnsupportedOperationError
from pab.core.models.agent import CanonicalAgentDefinition
from pab.core.models.execution import (
    ExecutionEvent,
    ExecutionHandle,
    ExecutionMode,
    ExecutionStatus,
    LaunchRequest,
    ProviderCapabilities,
)
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

    @abstractmethod
    def export_canonical_agent(self, agent_id: str) -> Optional[CanonicalAgentDefinition]:
        """Import a native agent definition from this provider and convert it into a CanonicalAgentDefinition."""
        pass


class AgentAdapter(AgentProvider):
    """Universal agent runtime adapter for lifecycle execution and supervision."""

    def discover(self) -> ProviderCapabilities:
        """Probe environment for executable or gateway and return detected capabilities."""
        detected = self.detect()
        ver = self.version() if detected else None
        caps = self.capabilities() if detected else {}
        ops = self.supported_operations()
        modes = self.supported_execution_modes()
        formats = caps.get("skill_formats", ["open-agent-skills"])
        health = "healthy" if detected else "unavailable"

        return ProviderCapabilities(
            provider=self.name,
            display_name=self.display_name,
            available=detected,
            detected_version=ver,
            executable_path=self.get_executable_path(),
            supported_operations=ops,
            supported_execution_modes=modes,
            supported_skill_formats=formats,
            detection_timestamp=datetime.now(timezone.utc),
            health_status=health,
            required_configuration=caps.get("required_configuration", {}),
            detection_errors=[],
        )

    def supported_operations(self) -> List[str]:
        """List of operations supported by this adapter."""
        ops = ["discover", "capabilities"]
        if hasattr(self, "export_session"):
            ops.append("export_session")
        if hasattr(self, "resume_session"):
            ops.append("resume")
        return ops

    def supported_execution_modes(self) -> List[str]:
        """List of execution modes supported by this adapter."""
        return [ExecutionMode.MANAGED_PROCESS.value]

    def get_executable_path(self) -> Optional[str]:
        """Return path to executable if detected."""
        return None

    def launch(self, request: LaunchRequest) -> ExecutionHandle:
        """Launch an agent process for the given execution request."""
        raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'launch'")

    def attach(self, execution_id: str) -> bool:
        """Attach to an already running provider session or process."""
        raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'attach'")

    def resume(self, session_id: str, context: Optional[Any] = None) -> ExecutionHandle:
        """Resume an existing session."""
        raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'resume'")

    def inspect(self, execution_id: str) -> ExecutionHandle:
        """Inspect running execution status."""
        raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'inspect'")

    def stream_events(self, execution_id: str) -> Iterator[ExecutionEvent]:
        """Yield real-time events for an execution."""
        raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'stream_events'")

    def send_input(self, execution_id: str, message: str) -> bool:
        """Deliver input message or response to an agent waiting for input."""
        raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'send_input'")

    def stop(self, execution_id: str, force: bool = False) -> bool:
        """Stop an active execution."""
        raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'stop'")

    def import_context(self, context: Any) -> bool:
        """Import portable context into provider."""
        raise UnsupportedOperationError(f"Provider '{self.name}' does not support 'import_context'")

