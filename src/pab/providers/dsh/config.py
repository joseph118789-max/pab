"""DeepSeek Shell (DSH) configuration and path discovery."""

import os
import shutil
from pathlib import Path
from typing import Optional


def get_dsh_home() -> Path:
    """Resolve DSH home directory, respecting DSH_HOME or defaulting to ~/.dsh."""
    env_home = os.environ.get("DSH_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".dsh").resolve()


def get_dsh_profiles_dir() -> Path:
    """Resolve DSH profiles directory."""
    return get_dsh_home() / "profiles"


def get_dsh_bin() -> Optional[str]:
    """Find binary executable for DSH."""
    which = shutil.which("dsh")
    if which:
        return which
    candidates = [
        Path.home() / ".local" / "bin" / "dsh",
        Path("/usr/local/bin/dsh"),
        Path("/usr/bin/dsh"),
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None
