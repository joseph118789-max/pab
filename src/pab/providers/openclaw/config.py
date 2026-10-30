"""OpenClaw configuration and path resolution."""

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional


def get_openclaw_home() -> Path:
    env_home = os.environ.get("OPENCLAW_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".openclaw").resolve()


def get_openclaw_bin() -> Optional[str]:
    return shutil.which("openclaw")


def read_openclaw_json(config_path: Optional[Path] = None) -> Dict[str, Any]:
    path = config_path or (get_openclaw_home() / "openclaw.json")
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_openclaw_json(data: Dict[str, Any], config_path: Optional[Path] = None) -> None:
    path = config_path or (get_openclaw_home() / "openclaw.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
