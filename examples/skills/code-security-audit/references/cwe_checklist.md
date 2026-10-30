# Security Review Checklist (Common CWEs)

When auditing code, verify the following security weaknesses:

## 1. Injection Vulnerabilities
- **CWE-89 (SQL Injection)**: Ensure all queries use parameterized inputs or ORM binding; never interpolate raw strings into SQL.
- **CWE-78 (OS Command Injection)**: Avoid `shell=True` in subprocess calls. Pass arguments as arrays/lists without shell wrapping.
- **CWE-79 (Cross-Site Scripting)**: Ensure proper output encoding and sanitization in HTML/web templates.

## 2. Broken Authentication & Secrets
- **CWE-798 (Hardcoded Credentials)**: Passwords, API tokens, and private keys must never be hardcoded in repository files.
- **CWE-384 (Session Fixation)**: Ensure secure session regeneration after login.

## 3. Insecure Deserialization & Execution
- **CWE-502 (Deserialization of Untrusted Data)**: Never use Python `pickle` or YAML `unsafe_load` on user input; use JSON or `yaml.safe_load`.
- **CWE-94 (Code Injection)**: Avoid dynamic `eval()`, `exec()`, or runtime code execution.

## 4. Path Traversal & File Access
- **CWE-22 (Path Traversal)**: Always resolve paths and check that `target.resolve().is_relative_to(base.resolve())` before reading or writing.
