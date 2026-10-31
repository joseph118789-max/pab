"""Pi Coding Agent configuration and path discovery."""

import os
import shutil
from pathlib import Path
from typing import Optional


def get_pi_home() -> Path:
    """Resolve Pi home directory, respecting PI_CODING_AGENT_DIR or defaulting to ~/.pi/agent."""
    env_home = os.environ.get("PI_CODING_AGENT_DIR")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".pi" / "agent").resolve()


def get_pi_sessions_dir() -> Path:
    """Resolve Pi sessions directory, respecting PI_CODING_AGENT_SESSION_DIR."""
    env_dir = os.environ.get("PI_CODING_AGENT_SESSION_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return get_pi_home() / "sessions"


def get_pi_bin() -> Optional[str]:
    """Find binary executable for Pi coding agent."""
    which = shutil.which("pi")
    if which:
        return which
    candidates = [
        Path.home() / ".local" / "bin" / "pi",
        Path("/usr/local/bin/pi"),
        Path("/usr/bin/pi"),
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None
