#!/usr/bin/env python3
"""Secret and credential scanner script for code repositories."""

import os
import re
import sys
from pathlib import Path

# Common high-entropy or pattern indicators (compiled safely)
SUSPICIOUS_KEY_PATTERNS = [
    re.compile(r"""(?:api[_-]?key|auth[_-]?token|secret[_-]?key)\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]""", re.IGNORECASE),
    re.compile(r"""-----BEGIN\s+[A-Z\s]+PRIVATE\s+KEY-----"""),
    re.compile(r"""(?:AKIA|ASIA)[0-9A-Z]{16}"""),
    re.compile(r"""ghp_[A-Za-z0-9]{36}"""),
]

EXCLUDE_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache"}


def scan_file(filepath: Path) -> list:
    findings = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    for line_num, line in enumerate(content.splitlines(), start=1):
        for pat in SUSPICIOUS_KEY_PATTERNS:
            if pat.search(line):
                findings.append((line_num, line.strip()[:80]))
                break
    return findings


def main():
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(f"Scanning directory: {target_dir}")
    total_findings = 0

    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            p = Path(root) / f
            findings = scan_file(p)
            if findings:
                print(f"\n[!] Findings in {p.relative_to(target_dir)}:")
                for lnum, line in findings:
                    print(f"    Line {lnum}: {line}")
                total_findings += len(findings)

    print(f"\nScan completed. Total potential secret findings: {total_findings}")
    sys.exit(0 if total_findings == 0 else 1)


if __name__ == "__main__":
    main()
