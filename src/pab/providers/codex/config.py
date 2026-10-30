"""OpenAI Codex CLI configuration and paths."""

import os
import shutil
from pathlib import Path
from typing import Optional


def get_codex_home() -> Path:
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def get_codex_bin() -> Optional[str]:
    which_bin = shutil.which("codex")
    if which_bin:
        return which_bin
    # Check openclaw managed codex if available
    cand = Path("/usr/local/bin/codex")
    if cand.is_file() and os.access(cand, os.X_OK):
        return str(cand)
    return None
