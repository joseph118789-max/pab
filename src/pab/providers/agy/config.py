"""Antigravity CLI (agy) configuration and paths."""

import os
import shutil
from pathlib import Path
from typing import Optional


def get_gemini_home() -> Path:
    env_home = os.environ.get("GEMINI_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".gemini").resolve()


def get_agy_config_dir() -> Path:
    return get_gemini_home() / "config"


def get_agy_cli_dir() -> Path:
    return get_gemini_home() / "antigravity-cli"


def get_agy_bin() -> Optional[str]:
    # Check PATH or default local locations
    which_bin = shutil.which("agy")
    if which_bin:
        return which_bin
    local_bin = Path.home() / ".local" / "bin" / "agy"
    if local_bin.is_file() and os.access(local_bin, os.X_OK):
        return str(local_bin)
    return None
