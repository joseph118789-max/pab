---
name: pab-ops
description: >-
  Universal operational runbook and instructions for PersonaOS Agent Bridge (PAB).
  Use whenever an AI agent needs to inspect, deploy, migrate, clone, or synchronise
  agents, skills, memories, and sessions across OpenClaw, Antigravity (agy), Codex, and Claude.
metadata:
  version: 1.0.0
  author: PersonaOS Agent Bridge Team
  tags:
    - agent-management
    - cross-platform
    - skill-sync
    - session-handoff
    - memory-hub
dependencies:
  - pab
  - python3
---

# PersonaOS Agent Bridge (PAB) Operational Skill

## Overview
PersonaOS Agent Bridge (PAB) is the universal control plane and management layer across four major AI agent platforms:
1. **OpenClaw**
2. **Google Antigravity CLI (`agy`)**
3. **OpenAI Codex CLI**
4. **Anthropic Claude Code**

This skill teaches the agent how to interact with the PAB CLI (`pab`) to maintain agent identities centrally, synchronise skills and memory, export cross-platform handoff bundles, and deploy agents without platform lock-in.

---

## When to Activate
Activate this skill when:
- Creating, importing, cloning, or deploying an agent profile.
- Synchronising or auditing Open Agent Skills across platforms.
- Querying shared project/agent memory across OpenClaw, Antigravity, Codex, or Claude.
- Handing off an active session from one platform (e.g. Antigravity) to another (e.g. OpenClaw).
- Verifying environment health, platform runtimes, and local configuration paths.
- Checking PAB architecture via [Architecture Cheat Sheet](references/architecture_cheat_sheet.md) or CLI syntax via [CLI Reference](references/cli_reference.md).

---

## Standard Operational Workflows

### 1. Health Diagnostics & Provider Discovery
Verify runtime availability and configuration health:
```bash
# Check all platforms and database connectivity
pab doctor

# Inspect detected platforms, versions, and capability matrices
pab providers list

# Quick status check using bundled script
python3 scripts/pab_quickcheck.py
```

### 2. Universal Agent Management

#### A. Import an Existing Agent into Canonical Registry
```bash
# Import OpenClaw's main agent
pab agent import main --from openclaw

# Or import from Antigravity, Codex, or Claude
pab agent import devops --from agy
```

#### B. Deploy an Agent to Platforms
```bash
# Deploy to all supported platforms
pab agent deploy main --to all

# Deploy specifically to Antigravity and Claude
pab agent deploy main --to agy,claude
```

#### C. Clone & Fork Agents
```bash
# Fork an agent for a specialized task
pab agent clone main dba-agent --name "Database Administrator"
```

#### D. Version Inspection, Diffing & Rollback
```bash
# Compare configuration across versions
pab agent diff main --version1 1.0.0 --version2 1.0.1

# Revert to a previous snapshot
pab agent rollback main 1.0.0
```

---

### 3. Cross-Platform Skill Management

#### A. Create and Validate a New Skill
```bash
# 1. Scaffold new skill
pab skill create <skill-name> --desc "<Description>"

# 2. Validate skill folder structure against Open Agent Skills spec
pab skill validate <skill-name>

# 3. Security audit for dangerous shell commands or credential leaks
pab skill audit <skill-name>
```

#### B. Universal Skill Deployment
```bash
# Deploy a single skill to all platforms
pab skill deploy <skill-name> --to all

# Synchronise all canonical skills to all platforms
pab skill sync --to all
```

---

### 4. Shared Memory Hub

#### A. Querying Knowledge Across Providers
```bash
# Search indexed memories across platforms
pab memory search "<query>"

# Search within specific scope (global, project, agent)
pab memory search "failover" --scope project
```

#### B. Ingesting Provider Memories
```bash
# Import native memories from OpenClaw, Antigravity, etc.
pab memory import openclaw
```
*Note: Imported memories are tagged with `untrusted: true` provenance to enforce zero-trust security boundaries.*

---

### 5. Session Migration & Cross-Platform Handoff
When migrating work from one agent provider to another:

```bash
# 1. Discover active sessions across platforms
pab session list

# 2. Export portable handoff bundle (HANDOFF.md + context.json)
pab session handoff --from agy <SESSION_ID>

# 3. The exported bundle can be fed into OpenClaw, Codex, or Claude Code
```

*Important: Native direct session resumption is strictly restricted to the same provider. Cross-platform transitions MUST use the portable handoff bundle.*

---

### 6. Unified Pre-Flight Launch
Perform pre-flight configuration validation and prepare launch context:
```bash
# Launch on OpenClaw
pab run main --provider openclaw

# Launch on Antigravity with handoff context
pab run main --provider agy --with-handoff <SESSION_ID>
```

---

## Troubleshooting Guide

| Issue | Cause | Fix |
| :--- | :--- | :--- |
| `pab: command not found` | Local bin directory not in `$PATH` | Add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc`. |
| `Provider not detected` | Executable or default directory missing | Run `pab doctor` to locate missing config paths. |
| `Audit findings in skill` | Risky pattern (e.g. untrusted remote pipe or unbounded deletion) | Replace with safe, bounded execution in script. |
| `Path traversal detected` | Relative path outside allowed root | Ensure target directories resolve inside workspace/home. |
