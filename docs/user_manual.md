# PersonaOS Agent Bridge (PAB) — User Manual
> **One management layer. Four agent platforms. One shared knowledge base.**

---

## 1. Introduction

### What is PersonaOS Agent Bridge (PAB)?
**PersonaOS Agent Bridge (PAB)** is a local-first universal control plane for creating, configuring, sharing, migrating, and managing AI agents across heterogeneous development environments. 

Rather than locking your autonomous agents, skills, and memory into a single vendor's ecosystem, PAB maintains a **canonical single source of truth** and compiles configurations into the native formats of supported AI agent platforms:
1. **OpenClaw** (Multi-channel AI agent gateway, workspaces, daily memory)
2. **Google Antigravity CLI (`agy`)** (Google DeepMind agent runtime, `agent.md`, progressive disclosure skills)
3. **OpenAI Codex CLI** (TOML custom-agent profiles, system skills, execution logs)
4. **Anthropic Claude Code** (Subagent Markdown frontmatter, `CLAUDE.md`, project memory)
5. **MiniMax Coding CLI (`mcode`)** (High-throughput coding agent, Markdown agents, skills)
6. **DeepSeek Shell (`dsh`)** (DeepSeek Harness, modular cordis profiles, skill registry)
7. **Pi Coding Agent (`pi`)** (Minimalist extensible harness, tree sessions, native `AGENTS.md`)

---

## 2. Installation & Getting Started

### Prerequisites
- Python 3.11 or later
- At least one supported AI CLI tool installed (`openclaw`, `agy`, `codex`, or `claude`)

### Installation
From the repository root (`/root/.openclaw/workspace/projects/pab`):
```bash
python3 -m pip install -e . --no-deps --break-system-packages
```
Ensure `pab` is available in your `$PATH`:
```bash
which pab
pab --version
```

### Initial Health Check (`pab doctor`)
Run the diagnostic probe to detect all installed agent platforms, inspect their versions, and verify storage readiness:
```bash
pab doctor
```

---

## 3. Storage Hierarchy

PAB stores its canonical state in `~/.pab/` (or `.pab/` within a project directory):

| Directory | Purpose |
| :--- | :--- |
| `config.yaml` | Global preferences, active providers, and storage roots |
| `pab.db` | SQLite database holding agent metadata, skill indices, session catalogs, and audit history |
| `agents/` | Canonical agent profiles (`agent.yaml`), instructions, and version snapshots |
| `skills/` | Open Agent Skills (`SKILL.md`, `scripts/`, `references/`, `assets/`) |
| `memory/` | Multi-tier markdown memory files (`global/`, `projects/`, `agents/`, `daily/`, `imports/`) |
| `sessions/` | Exported normalized sessions and portable handoff bundles |
| `backups/` | Automated point-in-time snapshots created prior to reconciliation operations |

---

## 4. CLI Command Reference

### A. Provider Inspection (`pab providers`)
```bash
# List detected providers and versions
pab providers list

# View capability matrix (optionally filter by provider)
pab providers capabilities
pab providers capabilities agy
```

### B. Agent Management (`pab agent`)
```bash
# 1. List canonical agents
pab agent list

# 2. Create a new canonical agent
pab agent create devops-engineer \
  --name "DevOps Engineer" \
  --role "Infrastructure Automation Specialist" \
  --desc "Automates cloud and container infrastructure" \
  --skills "kubernetes,ansible,linux"

# 3. View canonical agent profile (YAML output)
pab agent show devops-engineer

# 4. Deploy agent to one or more platforms
pab agent deploy devops-engineer --to openclaw
pab agent deploy devops-engineer --to agy,codex,claude
pab agent deploy devops-engineer --to all

# 5. Clone an existing agent
pab agent clone devops-engineer sre-engineer "Site Reliability Engineer"

# 6. Roll back to an earlier version
pab agent rollback devops-engineer --version 1.0.0

# 7. Delete an agent
pab agent delete sre-engineer --force
```

### C. Universal Skill Management (`pab skill`)
PAB adopts the **Open Agent Skills** specification (`SKILL.md` + optional `scripts/`, `references/`, `assets/`).

```bash
# 1. List skills in the central library
pab skill list

# 2. Create a new skill template
pab skill create kubernetes-ops --desc "Cluster diagnostics and pod inspection."

# 3. Validate metadata and references
pab skill validate kubernetes-ops

# 4. Perform automated security scanning (checks for dangerous commands or leaked tokens)
pab skill audit kubernetes-ops

# 5. Deploy skill to platforms
pab skill deploy kubernetes-ops --to all
pab skill deploy kubernetes-ops --to codex,claude

# 6. Synchronize all skills across all platforms
pab skill sync --to all

# 7. Import a skill folder from local disk
pab skill import ./my-custom-skill

# 8. Export a skill bundle to a target directory
pab skill export kubernetes-ops --to ./dist
```

### D. Instruction Management (`pab instruction`)
```bash
# 1. View canonical AGENTS.md
pab instruction show

# 2. Export instructions tailored to a native platform
pab instruction export --to claude --dir .   # Generates CLAUDE.md
pab instruction export --to agy --dir .      # Generates GEMINI.md
pab instruction export --to codex --dir .    # Generates AGENTS.md

# 3. Import and non-destructively merge external instructions
pab instruction import ./CLAUDE.md --from claude

# 4. Compare two instruction files and view conflicting sections
pab instruction compare ./AGENTS.md ./CLAUDE.md
```

### E. Unified Memory Hub (`pab memory`)
```bash
# 1. List memories (optionally filter by scope: user|global|project|agent|daily|imported|handoff)
pab memory list
pab memory list --scope global

# 2. Full-text search across all memories
pab memory search "postgres connection pool"
pab memory search "failover"

# 3. Import memories from a native provider (tagged 'untrusted' until reviewed)
pab memory import openclaw
pab memory import codex
pab memory import agy
pab memory import claude

# 4. Create a full snapshot backup of all memory tiers
pab memory backup
```

### F. Session Migration & Handoff (`pab session`)
```bash
# 1. Discover sessions across all providers
pab session list
pab session list --provider agy

# 2. Export and normalize a native session
pab session export --provider agy --session <session-id>

# 3. Build a Portable Handoff Package (HANDOFF.md + context.json)
pab session handoff \
  --from agy \
  --to openclaw \
  --session <session-id>

# 4. Inject handoff context into a target workspace
pab session import-context \
  --provider openclaw \
  --session <session-id> \
  --workspace ~/.openclaw/agents/devops

# 5. Resume session (strictly allowed only on identical native provider)
pab session resume --provider agy --session <session-id>
```

### G. Synchronisation Engine (`pab sync`)
```bash
# 1. Generate dry-run reconciliation plan
pab sync plan --to all
pab sync plan --to codex,claude

# 2. Apply an approved plan (automatically snapshots backup before applying)
pab sync apply <plan-id>
```

### H. Unified Agent Launch (`pab run`)
```bash
# Run agent on OpenClaw
pab run devops-engineer --provider openclaw

# Run agent on Google Antigravity CLI
pab run devops-engineer --provider agy

# Launch with in-flight handoff context injected
pab run devops-engineer --provider claude --with-handoff <session-id>
```

### I. PersonaOS Integration (`pab personaos`)
```bash
# Check provider readiness
pab personaos readiness

# Import a single worker profile
pab personaos import /root/projects/PersonaOS/profiles/worker-devops-001/v1.yaml

# Scan profiles directory, import all workers, and deploy to external platforms
pab personaos sync --dir /root/projects/PersonaOS/profiles --to all
```

### J. One-Command Agent Switching & Session Handoff

Switch seamlessly between OpenClaw, Google Antigravity (`agy`), OpenAI Codex, and Anthropic Claude Code with a single command. Automatically extracts working context, discovers the relevant session, synchronises skills and instructions, builds a portable handoff package (`.pab/handoffs/<id>/`), and launches the destination native CLI.

#### Primary Syntax
```bash
pab <target-agent> --from <source-agent>
```

#### Examples
```bash
# Switch to Codex from Claude Code
pab codex --from claude

# Switch to Antigravity CLI from Codex
pab agy --from codex

# Switch to Claude Code from OpenClaw
pab claude --from openclaw

# Switch to OpenClaw from Codex
pab openclaw --from codex

# Switch to Pi Coding Agent from Claude
pab pi --from claude

# Switch to DeepSeek Shell from Pi
pab dsh --from pi
```

#### Additional Options & Pass-Through Arguments
```bash
# Switch using specific session or latest project session
pab codex --from claude --session latest
pab codex --from claude --session <session-id>

# Switch modes: handoff (default), clone (replicate identity), or skills-only
pab codex --from claude --mode handoff
pab codex --from claude --mode clone
pab codex --from claude --mode skills-only

# Target specific project directory or agent
pab codex --from claude --project /path/to/project --agent devops

# Selectively skip skills or memory
pab codex --from claude --no-skills
pab codex --from claude --no-memory

# Dry-run migration plan without spawning native CLI
pab codex --from claude --dry-run

# Direct launch without migration
pab codex
pab claude
pab agy
pab openclaw

# Native argument pass-through (separated by --)
pab codex --from claude -- --full-auto
```

#### Switching State, History & Rollback
```bash
# View complete switching history
pab switch history

# Inspect handoff manifest, file hashes, and context
pab switch inspect <handoff-id>

# Roll back PAB-managed handoff configuration safely
pab switch rollback <handoff-id>
```

---

## 5. Security & Isolation Model

PAB is designed local-first with defense-in-depth safety:
1. **Secret Redaction**: API keys (`sk-...`, `ghp_...`, Bearer tokens, passwords) are automatically redacted when generating handoff packages and exports.
2. **Untrusted Import Tagging**: Content imported from external provider sessions or memories is marked `untrusted: true` until verified by a human operator, preventing indirect prompt injections.
3. **Path Traversal Protection**: All paths are validated against allowed workspace boundaries using canonical path resolution.
4. **Pre-Sync Snapshots**: Every `pab sync apply` creates an automatic point-in-time backup in `~/.pab/backups/`.
