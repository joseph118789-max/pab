"""MiniMax Coding CLI configuration and path discovery."""

import os
import shutil
from pathlib import Path
from typing import Optional


def get_minimax_home() -> Path:
    """Resolve MiniMax home directory, respecting MINIMAX_HOME or defaulting to ~/.minimax."""
    env_home = os.environ.get("MINIMAX_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".minimax").resolve()


def get_minimax_bin() -> Optional[str]:
    """Resolve mcode executable path."""
    bin_path = shutil.which("mcode")
    if bin_path:
        return bin_path
    cand = Path("/usr/bin/mcode")
    if cand.is_file() and os.access(cand, os.X_OK):
        return str(cand)
    return None
