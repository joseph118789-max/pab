"""Provider detection, inventory, and health checks."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.providers.agy.adapter import AgyAdapter
from pab.providers.base import AgentProvider
from pab.providers.claude.adapter import ClaudeAdapter
from pab.providers.codex.adapter import CodexAdapter
from pab.providers.minimax.adapter import MinimaxAdapter
from pab.providers.openclaw.adapter import OpenClawAdapter


class ProviderRegistry:
    """Central registry and detector for provider adapters."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root
        self._providers: Dict[str, AgentProvider] = {
            "openclaw": OpenClawAdapter(),
            "agy": AgyAdapter(workspace_root=workspace_root),
            "codex": CodexAdapter(workspace_root=workspace_root),
            "claude": ClaudeAdapter(workspace_root=workspace_root),
            "minimax": MinimaxAdapter(workspace_root=workspace_root),
        }

    def get(self, name: str) -> Optional[AgentProvider]:
        return self._providers.get(name.lower())

    def list_all(self) -> List[AgentProvider]:
        return list(self._providers.values())

    def detect_all(self) -> Dict[str, Dict[str, Any]]:
        status = {}
        for name, provider in self._providers.items():
            detected = provider.detect()
            version = provider.version() if detected else None
            status[name] = {
                "name": name,
                "display_name": provider.display_name,
                "detected": detected,
                "version": version,
                "capabilities": provider.capabilities() if detected else {},
            }
        return status
