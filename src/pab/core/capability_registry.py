"""PAB Provider Capability Registry.

Maintains dynamic, verified capability records for external agent runtimes.
Scans binaries, probes version outputs, and enumerates supported operations
without hardcoding capabilities.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pab.core.models.execution import ExecutionMode, ProviderCapabilities
from pab.providers.base import AgentAdapter, AgentProvider
from pab.providers.detector import ProviderRegistry


class CapabilityRegistry:
    """Discovers, inventories, and evaluates provider runtime capabilities."""

    def __init__(self, provider_registry: Optional[ProviderRegistry] = None):
        self._provider_registry = provider_registry or ProviderRegistry()

    @property
    def provider_registry(self) -> ProviderRegistry:
        return self._provider_registry

    def register_provider(self, name: str, provider: AgentProvider) -> None:
        """Register or override an adapter (useful for mocks or extensions)."""
        self._provider_registry._providers[name.lower()] = provider

    def get_capabilities(self, provider_name: str) -> Optional[ProviderCapabilities]:
        """Fetch verified capabilities for a single provider."""
        provider = self._provider_registry.get(provider_name)
        if not provider:
            return None
        return self._evaluate_provider(provider)

    def detect_all(self) -> Dict[str, ProviderCapabilities]:
        """Probe and return capabilities for all registered providers."""
        results: Dict[str, ProviderCapabilities] = {}
        for provider in self._provider_registry.list_all():
            results[provider.name] = self._evaluate_provider(provider)
        return results

    def list_capabilities(self) -> List[ProviderCapabilities]:
        """Return list of evaluated provider capabilities."""
        return list(self.detect_all().values())

    def _evaluate_provider(self, provider: AgentProvider) -> ProviderCapabilities:
        """Evaluate provider dynamically without assuming capability."""
        # If provider implements modern discover(), use it
        if isinstance(provider, AgentAdapter):
            return provider.discover()

        # Otherwise evaluate dynamically using AgentProvider protocol
        detected = provider.detect()
        ver = provider.version() if detected else None
        caps = provider.capabilities() if detected else {}

        executable_path = None
        # Try to resolve binary from which
        bin_candidates = {
            "openclaw": "openclaw",
            "agy": "agy",
            "codex": "codex",
            "claude": "claude",
            "minimax": "mcode",
            "dsh": "dsh",
            "pi": "pi",
        }
        cand = bin_candidates.get(provider.name, provider.name)
        which_path = shutil.which(cand)
        if which_path:
            executable_path = which_path
        else:
            local_cand = Path.home() / ".local" / "bin" / cand
            if local_cand.is_file() and os.access(local_cand, os.X_OK):
                executable_path = str(local_cand)

        supported_ops = ["discover", "capabilities"]
        if caps.get("agent_management"):
            supported_ops.extend(["list_agents", "get_agent", "create_agent", "update_agent", "delete_agent"])
        if caps.get("skills"):
            supported_ops.extend(["list_skills", "install_skill", "remove_skill"])
        if caps.get("sessions"):
            supported_ops.extend(["list_sessions", "export_session"])
        if caps.get("native_resume"):
            supported_ops.append("resume")

        skill_formats = ["open-agent-skills"]
        if provider.name == "codex":
            skill_formats.append("codex-toml")
        elif provider.name == "claude":
            skill_formats.append("claude-md")
        elif provider.name == "agy":
            skill_formats.append("gemini-rules")
        elif provider.name == "openclaw":
            skill_formats.append("openclaw-plugin")

        health = "healthy" if detected else "unavailable"
        detection_errors = []
        if detected and not ver:
            detection_errors.append(f"Executable found at {executable_path} but failed to report version.")
            health = "degraded"

        return ProviderCapabilities(
            provider=provider.name,
            display_name=provider.display_name,
            available=detected,
            detected_version=ver,
            executable_path=executable_path,
            supported_operations=supported_ops,
            supported_execution_modes=[ExecutionMode.MANAGED_PROCESS.value, ExecutionMode.ORCA_TERMINAL.value],
            supported_skill_formats=skill_formats,
            detection_timestamp=datetime.now(timezone.utc),
            health_status=health,
            required_configuration=caps.get("required_configuration", {}),
            detection_errors=detection_errors,
        )
