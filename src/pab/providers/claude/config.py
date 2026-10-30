"""Anthropic Claude Code configuration and paths."""

import os
import shutil
from pathlib import Path
from typing import Optional


def get_claude_home() -> Path:
    env_home = os.environ.get("CLAUDE_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".claude").resolve()


def get_claude_bin() -> Optional[str]:
    return shutil.which("claude")
