"""Target provider native CLI launcher."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from pab.core.exceptions import ProviderExecutionError


def resolve_provider_bin(provider_name: str) -> Optional[str]:
    """Find binary executable for provider."""
    bin_map = {
        "openclaw": ["openclaw"],
        "agy": ["agy"],
        "codex": ["codex"],
        "claude": ["claude"],
        "minimax": ["mcode", "minimax"],
        "dsh": ["dsh"],
        "pi": ["pi"],
    }
    candidates = bin_map.get(provider_name.lower(), [provider_name])
    for cand in candidates:
        which = shutil.which(cand)
        if which:
            return which
        local_cand = Path.home() / ".local" / "bin" / cand
        if local_cand.is_file() and os.access(local_cand, os.X_OK):
            return str(local_cand)
    return None


def build_launch_command(
    provider_name: str,
    handoff_instruction: Optional[str],
    handoff_md_path: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
) -> List[str]:
    """Build the provider-specific startup command."""
    bin_path = resolve_provider_bin(provider_name) or provider_name
    cmd = [bin_path]

    extra = extra_args or []

    # Provider specific flags
    p = provider_name.lower()
    if p == "claude":
        if handoff_instruction and not any(arg in extra for arg in ["-p", "--prompt"]):
            # Pass prompt if not already supplied
            cmd.extend(["-p", handoff_instruction])
    elif p == "codex":
        if handoff_instruction:
            cmd.extend([handoff_instruction])
    elif p == "agy":
        if handoff_instruction and not any(arg in extra for arg in ["-p", "--prompt"]):
            cmd.extend(["--prompt", handoff_instruction])
    elif p == "openclaw":
        pass
    elif p == "pi":
        if handoff_instruction and not any(arg in extra for arg in ["-p", "--print"]):
            cmd.extend(["-p", handoff_instruction])
    elif p == "dsh":
        if handoff_instruction and not any(arg in extra for arg in ["headless", "tui", "web"]):
            cmd.extend(["headless", handoff_instruction])

    # Append any user pass-through args
    cmd.extend(extra)
    return cmd


def execute_native_launch(
    launch_cmd: List[str],
    cwd: Path,
    env_vars: Optional[Dict[str, str]] = None,
) -> int:
    """Launch the destination native CLI in the project directory."""
    bin_name = launch_cmd[0]
    if not shutil.which(bin_name) and not Path(bin_name).is_file():
        raise ProviderExecutionError(
            f"Cannot launch {bin_name}: executable not found on PATH or ~/.local/bin."
        )

    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    proc = subprocess.run(launch_cmd, cwd=str(cwd), env=env)
    return proc.returncode
