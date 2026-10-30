"""Skill security scanner for dangerous scripts and leaked credentials."""

import re
from pathlib import Path
from typing import Any, Dict, List
from pab.core.models.skill import CanonicalSkill
from pab.core.security import SECRET_PATTERNS

RISKY_PATTERNS = [
    (re.compile(r"curl\s+[^\n|]+\|\s*(sh|bash)", re.IGNORECASE), "High: Piping curl directly into shell"),
    (re.compile(r"wget\s+[^\n|]+\|\s*(sh|bash)", re.IGNORECASE), "High: Piping wget directly into shell"),
    (re.compile(r"rm\s+-rf\s+(/|\$HOME|~|\*)", re.IGNORECASE), "Critical: Unbounded destructive recursive deletion"),
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE), "Critical: Fork bomb detected"),
    (re.compile(r"chmod\s+(-R\s+)?777", re.IGNORECASE), "Medium: Insecure world-writable permission assignment"),
    (re.compile(r"\b(nc|netcat)\s+-[le]", re.IGNORECASE), "High: Reverse shell command detected"),
]


def scan_skill_security(skill: CanonicalSkill) -> Dict[str, Any]:
    """Scan skill body and attached scripts for security risks."""
    findings: List[Dict[str, str]] = []

    # Check body for secrets and dangerous patterns
    for pattern, desc in RISKY_PATTERNS:
        if pattern.search(skill.body):
            findings.append({"target": "SKILL.md", "type": "risky_command", "detail": desc})

    for pat in SECRET_PATTERNS:
        if pat.search(skill.body):
            findings.append({"target": "SKILL.md", "type": "credential_leak", "detail": "Potential secret or API key exposed in skill markdown"})

    # Check attached scripts if source path exists
    if skill.source_path:
        src = Path(skill.source_path)
        for s in skill.scripts:
            f = src / s.relative_path
            if f.is_file():
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    for pattern, desc in RISKY_PATTERNS:
                        if pattern.search(content):
                            findings.append({"target": s.relative_path, "type": "risky_command", "detail": desc})
                    for pat in SECRET_PATTERNS:
                        if pat.search(content):
                            findings.append({"target": s.relative_path, "type": "credential_leak", "detail": "Exposed credential in script"})
                except Exception:
                    pass

    return {
        "skill": skill.manifest.name,
        "is_safe": len(findings) == 0,
        "findings_count": len(findings),
        "findings": findings,
    }
