# PersonaOS Agent Bridge (PAB)

> **One management layer. Four agent platforms. One shared knowledge base.**

PersonaOS Agent Bridge (PAB) is a local-first universal control plane for creating, configuring, sharing, migrating, and managing AI agents across heterogeneous AI CLI runtimes:

- 🦞 **OpenClaw** (Gateway, multi-channel agents, workspaces, daily memory)
- 🌐 **Google Antigravity CLI (`agy`)** (DeepMind runtime, `agent.md`, progressive disclosure skills)
- 💻 **OpenAI Codex CLI** (TOML custom-agent profiles, system skills, execution logs)
- 🧠 **Anthropic Claude Code** (Subagent Markdown frontmatter, `CLAUDE.md`, project memory)
- ⚡ **MiniMax Coding CLI (`mcode`)** (High-throughput coding agent, Markdown agents, skills)
- 🚀 **DeepSeek Shell (`dsh`)** (DeepSeek Harness, modular cordis profiles, skill registry)
- 🥧 **Pi Coding Agent (`pi`)** (Minimalist extensible harness, tree sessions, native `AGENTS.md`)

Instead of locking agent identities, prompt engineering, skills, and memory into a single vendor's proprietary runtime, PAB maintains a **canonical single source of truth** and compiles configurations into each platform's native format.

```
+------------------------------------------------------------------------+
|                      PersonaOS Agent Bridge (PAB)                      |
|   Canonical Profiles  ·  Skill Library  ·  Memory Hub  ·  Handoffs    |
+------------------------------------------------------------------------+
          |                      |                   |              |
          v                      v                   v              v
      OpenClaw              Antigravity            Codex          Claude
  (openclaw.json)       (.agents/agent.md)         (TOML)       (Markdown)
```

---

## Quick Start

### Installation
```bash
python3 -m pip install -e . --no-deps --break-system-packages
```

### Health Diagnostics
```bash
# Verify environment health, database connectivity, and detected platform CLIs
pab doctor

# List provider capability matrices
pab providers list
pab providers capabilities
```

---

## Real-World Example Use Cases

### Use Case 1: "Write Once, Run Anywhere" Agent Lifecycle

**The Problem:** You have developed an expert DevOps Engineer persona with custom system prompts, safety policies, and assigned skills. Currently, you must rewrite this configuration across `openclaw.json`, Antigravity `.agents/agent.md`, Codex TOML files, and Claude subagent Markdown templates.

**With PAB:** Create the agent once centrally and deploy it natively across all platforms.

#### 1. Create or Import the Agent
```bash
# Option A: Import an existing native agent (e.g., from OpenClaw)
pab agent import main --from openclaw

# Option B: Create a brand new canonical agent profile
pab agent create devops-engineer \
  --name "DevOps Engineer" \
  --role "Senior Infrastructure Automation Specialist" \
  --desc "Automates Kubernetes, Terraform, and CI/CD pipelines" \
  --skills "kubernetes,ansible,linux,docker"
```

#### 2. Deploy to All Platforms
```bash
pab agent deploy devops-engineer --to all
```

#### 3. Inspect Native Platform Configurations Generated
PAB automatically translates the canonical definition into native formats:
- **OpenClaw:** Registered in `~/.openclaw/openclaw.json` and `~/.openclaw/agents/devops-engineer/`.
- **Google Antigravity CLI (`agy`):** Compiled to `.agents/agents/devops-engineer/agent.md`.
- **OpenAI Codex:** Compiled to `~/.codex/agents/devops-engineer.toml`.
- **Anthropic Claude Code:** Compiled to `~/.claude/agents/devops-engineer.md` with YAML frontmatter.

#### 4. Audit Diffs and Roll Back Changes
```bash
# Compare versions when instructions change
pab agent diff devops-engineer --version1 1.0.0 --version2 1.0.1

# Revert to a previous stable snapshot
pab agent rollback devops-engineer 1.0.0
```

---

### Use Case 2: Authoring, Auditing, and Distributing Open Agent Skills

**The Problem:** You wrote an internal tool or operational runbook (e.g., database failover checks, secret auditing). Each platform expects different folder structures, and running unvetted community skills can expose your system to destructive commands (`rm -rf /`, `curl | bash`) or leaked tokens.

**With PAB:** Adopt the **Open Agent Skills** specification (`SKILL.md`), run automated security screening, and distribute the skill universally.

#### 1. Scaffold a New Skill Template
```bash
pab skill create code-security-audit \
  --desc "Comprehensive security auditing, secret leakage detection, and vulnerability scanning."
```

#### 2. Add Deterministic Scripts and Reference Documents
```
~/.pab/skills/code-security-audit/
├── SKILL.md                 # Progressive disclosure instructions for the agent
├── scripts/
│   └── scan_secrets.py      # Executable AST and pattern scanner
└── references/
    └── cwe_checklist.md     # Reference guide (CWE-89, CWE-78, CWE-22)
```

#### 3. Validate & Security Audit
```bash
# Validate against Open Agent Skills specification
pab skill validate code-security-audit

# Screen for destructive bash patterns, reverse shells, and credentials
pab skill audit code-security-audit
```

#### 4. Universal Deployment & Synchronisation
```bash
# Deploy to all 4 platforms simultaneously
pab skill deploy code-security-audit --to all

# Or synchronise the entire skill library across all platforms
pab skill sync --to all
```
*Result:* Immediately available in OpenClaw workspace/plugin skills, Antigravity `.agents/skills/`, Codex `~/.codex/skills/`, and Claude Code `~/.claude/skills/`.

---

### Use Case 3: Zero-Trust Cross-Platform Shared Memory Hub

**The Problem:** Critical project context, deployment notes, and architectural decisions are fragmented across OpenClaw daily logs, Antigravity conversation memories, and Claude memory files.

**With PAB:** Ingest and index multi-tier knowledge in a unified SQLite and markdown hub while maintaining zero-trust isolation.

#### 1. Ingest Provider Memories
```bash
# Ingest 380+ OpenClaw memories
pab memory import openclaw

# Ingest Antigravity and Claude memories
pab memory import agy
pab memory import claude
```
> **Security Note:** Imported memories are tagged with `untrusted: true` provenance to defend against indirect prompt injection until reviewed.

#### 2. Full-Text Search Across All Accumulated Knowledge
```bash
# Search across all platforms for incident context
pab memory search "postgres connection pool"
pab memory search "database failover cluster"

# Filter by scope (global, project, or agent)
pab memory search "backup retention policy" --scope project
```

---

### Use Case 4: Seamless Cross-Platform Session Handoff (Break Vendor Lock-In)

**The Problem:** You start a complex debugging task with Google Antigravity CLI (`agy`). You reach token limits, or need a specific capability from OpenClaw or Claude Code. Starting from scratch in the other tool loses all context, error logs, and file analysis.

**With PAB:** Generate a normalized, portable **Handoff Bundle** (`HANDOFF.md` + `context.json`) with secret redaction.

#### 1. Discover Active Sessions Across Providers
```bash
pab session list
```

#### 2. Export a Portable Handoff Bundle
```bash
# Export active Antigravity session into a cross-platform handoff bundle
pab session handoff --from agy a951ccf1-147d-4e2b-aaf9-46865774aa90
```
This produces a sanitized bundle:
- `HANDOFF.md`: Summary of task objective, current state, key findings, and next steps.
- `context.json`: Structured normalized message trajectory with secrets automatically redacted (`[REDACTED]`).

#### 3. Resume and Launch Seamlessly in Another Platform
```bash
# Launch OpenClaw agent with the exported handoff context injected
pab run main --provider openclaw --with-handoff a951ccf1-147d-4e2b-aaf9-46865774aa90

# Or launch in Claude Code
pab run main --provider claude --with-handoff a951ccf1-147d-4e2b-aaf9-46865774aa90
```

---

### Use Case 5: One-Command Agent Switching & Session Handoff

**The Problem:** You are deep in a development session in Claude Code or OpenClaw, but want to switch to OpenAI Codex or Antigravity (`agy`) to test a different model or specialized tool. Manually exporting history, copy-pasting memory, re-installing skills, and finding the right project folder is tedious and error-prone.

**With PAB:** Switch providers with a single command. PAB automatically discovers the relevant project session, extracts context, synchronises skills with version-conflict protection, builds an isolated handoff package (`.pab/handoffs/<id>/`), and launches the destination native CLI with continuing instructions.

```bash
# 1. Switch directly between agent CLIs
pab codex --from claude
pab agy --from codex
pab claude --from openclaw
pab openclaw --from codex

# 2. Pass flags directly through to the destination CLI (using --)
pab codex --from claude -- --full-auto

# 3. Custom modes (handoff, clone, skills-only) and dry-run verification
pab codex --from claude --mode handoff --dry-run
pab agy --from openclaw --mode skills-only

# 4. Audit switching history, inspect bundle manifests, or roll back safely
pab switch history
pab switch inspect switch-claude-to-codex-20261031-005110
pab switch rollback switch-claude-to-codex-20261031-005110
```

---

### Use Case 6: PersonaOS Worker Pool Onboarding

**The Problem:** Your autonomous workflow engine (PersonaOS) defines worker specifications in declarative profiles (`v1.yaml`), but you need to provision those workers across local developer CLI environments.

**With PAB:** Bridge PersonaOS worker leases to executable agent platform configurations.

```bash
# 1. Verify environment readiness
pab personaos readiness

# 2. Ingest worker profiles from PersonaOS
pab personaos import /root/projects/PersonaOS/profiles/worker-devops-001/v1.yaml

# 3. Synchronise all workers and auto-provision required skills across CLI tools
pab personaos sync --dir /root/projects/PersonaOS/profiles --to all
```

---

## Platform Storage & Discovery Mapping

| Platform | Agent Config Location | Skills Location | Instructions |
| :--- | :--- | :--- | :--- |
| **OpenClaw** | `~/.openclaw/openclaw.json`<br>`~/.openclaw/agents/<id>/` | `~/.openclaw/workspace/skills/`<br>`~/.openclaw/plugin-skills/` | `AGENTS.md`<br>`SOUL.md`<br>`USER.md` |
| **Antigravity (`agy`)** | `.agents/agents/<id>/agent.md`<br>`~/.gemini/config/agents/` | `.agents/skills/<id>/`<br>`~/.gemini/config/skills/` | `GEMINI.md`<br>`AGENTS.md` |
| **OpenAI Codex** | `~/.codex/agents/<id>.toml` | `.agents/skills/<id>/`<br>`~/.codex/skills/` | `AGENTS.md` |
| **Anthropic Claude Code** | `~/.claude/agents/<id>.md`<br>`.claude/agents/<id>.md` | `.claude/skills/<id>/`<br>`~/.claude/skills/` | `CLAUDE.md` |
| **MiniMax (`mcode`)** | `~/.minimax/agents/<id>/`<br>`.minimax/agents/<id>/` | `~/.minimax/skills/<id>/`<br>`.minimax/skills/<id>/` | `AGENTS.md` |
| **DeepSeek Shell (`dsh`)** | `~/.dsh/profiles/<id>/`<br>`.dsh/agents/<id>/` | `~/.dsh/skills/<id>/`<br>`.dsh/skills/<id>/` | `AGENTS.md`<br>`DEEPSEEK.md` |
| **Pi Coding Agent (`pi`)** | `~/.pi/agent/agents/<id>.json`<br>`.pi/agents/` | `~/.pi/agent/skills/<id>/`<br>`.pi/skills/` | `AGENTS.md`<br>`CLAUDE.md` |

---

## Security & Isolation Model

PAB is built local-first with defense-in-depth security principles:
1. **Automated Secret Redaction:** API keys (`sk-...`, `ghp_...`, AWS keys, Bearer tokens) are redacted from memory dumps and session handoff packages.
2. **Untrusted Import Quarantine:** Content imported from foreign agent platforms is quarantined with `untrusted: true` provenance to defend against indirect prompt injection.
3. **Path Traversal Protection:** All directory operations enforce strict boundary checks (`target.relative_to(root)`).
4. **Pre-Reconciliation Snapshots:** Automated backups are stored in `~/.pab/backups/` before any multi-provider synchronization is applied.

---

## Documentation

- 📖 [Comprehensive User Manual](docs/user_manual.md)
- 🏛️ [Architecture Specification](docs/architecture.md)
- 📊 [Platform Capability Matrix](docs/capability_matrix.md)
- 📜 [Architecture Decision Records (ADRs)](docs/adr/)
