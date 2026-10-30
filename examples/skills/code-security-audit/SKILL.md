---
name: code-security-audit
description: Comprehensive security auditing, secret leakage detection, and vulnerability scanning for codebases.
metadata:
  version: 1.0.0
  author: PAB Skill Library
  tags:
    - security
    - static-analysis
    - compliance
    - secrets
dependencies:
  - python3
---

# Code Security Audit Skill

## Overview
This skill instructs the agent on conducting rigorous security reviews, secret detection, dependency audits, and common vulnerability remediation across software projects.

## When to Activate
Activate this skill when:
- Conducting pre-release or pull request security reviews.
- Auditing a repository for exposed credentials, API keys, or private certificates.
- Validating dependencies for known CVEs.
- Verifying code against common CWEs (SQLi, Command Injection, Path Traversal).

---

## Step-by-Step Security Audit Workflow

### 1. Secret & Key Scanning
Inspect the repository for hardcoded credentials, API tokens, and private keys.
Run the bundled scanner script:
```bash
python3 scripts/scan_secrets.py .
```
Key patterns to watch for:
- Cloud provider keys (`AKIA...`, `ASIA...`)
- Git provider personal access tokens (`ghp_...`, `glpat-...`)
- Private key headers (`-----BEGIN ... PRIVATE KEY-----`)
- High-entropy tokens in `.env`, config, or test fixture files.

### 2. Injection & Unsafe Execution Checks
Inspect source code against [CWE Checklist](references/cwe_checklist.md):
- Search for dynamic execution: `eval(`, `exec(`, `os.system(`, `shell=True`.
- Search for raw SQL concatenations: `SELECT ... WHERE ... %s` or f-strings in queries.
- Check path handling: Ensure all file writes validate target directory bounds to prevent path traversal (`../`).

### 3. Dependency Vulnerability Audit
Execute native package vulnerability tools:
- **Python**: Run `pip audit` or inspect lockfiles (`poetry.lock`, `requirements.txt`).
- **Node.js**: Run `npm audit` or `pnpm audit`.
- Verify that pinned versions do not have published high/critical CVEs.

### 4. Remediation & Reporting
When vulnerabilities are identified:
1. Document the exact file, line number, and CWE identifier.
2. Provide a concrete, drop-in remediation code snippet.
3. Recommend secret rotation immediately if live tokens were discovered in git history or tracked files.
