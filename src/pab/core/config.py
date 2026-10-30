"""PAB Configuration and Path Management."""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field


class PABSettings(BaseModel):
    version: str = "1.0"
    default_provider: str = "openclaw"
    enabled_providers: list[str] = Field(
        default_factory=lambda: ["openclaw", "agy", "codex", "claude"]
    )
    auto_backup: bool = True
    strict_security: bool = True
    storage_root: Optional[str] = None
    custom: Dict[str, Any] = Field(default_factory=dict)


def get_default_pab_dir() -> Path:
    """Resolve PAB home directory, respecting PAB_HOME or defaulting to ~/.pab."""
    env_home = os.environ.get("PAB_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".pab").resolve()


def get_workspace_pab_dir(cwd: Optional[Path] = None) -> Optional[Path]:
    """Check if the current workspace or parent repo contains a .pab directory."""
    current = (cwd or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / ".pab"
        if candidate.is_dir():
            return candidate
        if (directory / ".git").is_dir():
            break
    return None


class ConfigManager:
    """Manages PAB directories, settings, and persistence."""

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir:
            self.root = root_dir.expanduser().resolve()
        else:
            self.root = get_workspace_pab_dir() or get_default_pab_dir()
        self.config_file = self.root / "config.yaml"
        self.db_path = self.root / "pab.db"
        self.agents_dir = self.root / "agents"
        self.skills_dir = self.root / "skills"
        self.memory_dir = self.root / "memory"
        self.instructions_dir = self.root / "instructions"
        self.sessions_dir = self.root / "sessions"
        self.backups_dir = self.root / "backups"
        self.settings = self._load_or_create()

    def ensure_directories(self) -> None:
        """Create necessary directory layout."""
        for path in [
            self.root,
            self.agents_dir,
            self.skills_dir,
            self.memory_dir,
            self.memory_dir / "global",
            self.memory_dir / "projects",
            self.memory_dir / "agents",
            self.memory_dir / "daily",
            self.memory_dir / "imports",
            self.instructions_dir,
            self.sessions_dir,
            self.sessions_dir / "exports",
            self.sessions_dir / "handoffs",
            self.backups_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def _load_or_create(self) -> PABSettings:
        self.ensure_directories()
        if not self.config_file.exists():
            settings = PABSettings(storage_root=str(self.root))
            self.save_settings(settings)
            return settings
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return PABSettings(**data)
        except Exception:
            return PABSettings(storage_root=str(self.root))

    def save_settings(self, settings: PABSettings) -> None:
        self.ensure_directories()
        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(settings.model_dump(), f, sort_keys=False)
        self.settings = settings
