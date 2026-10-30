"""Security, secret redaction, and safe path validation."""

import os
import re
from pathlib import Path
from typing import Union


SECRET_PATTERNS = [
    re.compile(r"(api[-_]?key\s*[:=]\s*['\"]?)([\w\-]{16,})(['\"]?)", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*['\"]?)([\w\-]{16,})(['\"]?)", re.IGNORECASE),
    re.compile(r"(secret\s*[:=]\s*['\"]?)([\w\-]{16,})(['\"]?)", re.IGNORECASE),
    re.compile(r"(password\s*[:=]\s*['\"]?)([^\s'\"]{6,})(['\"]?)", re.IGNORECASE),
    re.compile(r"(bearer\s+)([\w\-\.]{20,})", re.IGNORECASE),
    re.compile(r"(ghp_[a-zA-Z0-9]{36})", re.IGNORECASE),
    re.compile(r"(sk-[a-zA-Z0-9]{32,})", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Redact sensitive keys and credentials in text."""
    redacted = text
    for pattern in SECRET_PATTERNS:
        def _replace(match):
            groups = match.groups()
            if len(groups) == 3:
                return f"{groups[0]}[REDACTED]{groups[2]}"
            elif len(groups) == 2:
                return f"{groups[0]}[REDACTED]"
            return "[REDACTED]"
        redacted = pattern.sub(_replace, redacted)
    return redacted


def validate_safe_path(target_path: Union[str, Path], allowed_root: Union[str, Path]) -> Path:
    """Validate that target_path is within allowed_root and prevents path traversal."""
    root = Path(allowed_root).resolve()
    target = Path(target_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(f"Path traversal detected: {target_path} is outside {allowed_root}")
    return target


def ensure_secure_permissions(path: Path) -> None:
    """Set 0o700 for directories and 0o600 for sensitive files."""
    if not path.exists():
        return
    try:
        if path.is_dir():
            os.chmod(path, 0o700)
        else:
            os.chmod(path, 0o600)
    except OSError:
        pass
