# PersonaOS Agent Bridge (PAB) Architecture

## 1. Overview
PersonaOS Agent Bridge (PAB) provides a unified management and configuration control plane for heterogeneous AI agent platforms:
- **OpenClaw**
- **Google Antigravity CLI (`agy`)**
- **OpenAI Codex CLI**
- **Anthropic Claude Code**

PAB decouples agent identity, capabilities, instructions, skills, memory, and sessions from individual provider runtimes.

## 2. Core Modules
1. **Agent Registry**: Central source of truth for canonical agent profiles, versioning, diff, and rollback.
2. **Skill Manager**: Universal skill repository adopting the Open Agent Skills specification (`SKILL.md`), scripts, assets, references, validation, conversion, and deployment.
3. **Memory Hub**: Shared multi-tier knowledge repository (User, Global, Project, Agent, Daily, Imported, Handoff) with content hashing, deduplication, search, and security isolation.
4. **Instruction Manager**: Centralized management of `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and OpenClaw identity/bootstrap files (`SOUL.md`, `IDENTITY.md`, `USER.md`).
5. **Session Migration Manager**: Cross-platform session discovery, export, normalization, and generation of Portable Handoff Bundles (`HANDOFF.md`, `context.json`, `workspace.diff`).
6. **Provider Adapters**: Individual platform adapters that inspect system environments, translate canonical profiles into native formats, and execute native commands.
7. **Sync Engine**: Reconciliation engine for previewing diffs, planning changes, running backups, and applying updates atomically.
8. **PersonaOS Bridge**: Direct integration with PersonaOS worker profiles (`v1.yaml`) to bridge internal workers with external agent execution environments.

## 3. Storage Hierarchy
PAB stores configuration in `~/.pab/` (or `.pab/` for project-local overrides):
- `config.yaml`: Global settings, active providers, default paths.
- `pab.db`: SQLite database for agent registry, skill indices, session catalog, audit history.
- `agents/`: Canonical YAML agent profiles with version history.
- `skills/`: Reusable skills in canonical Open Agent Skills format.
- `memory/`: Tiered markdown memory files.
- `sessions/`: Exported transcripts and generated portable handoff packages.
- `backups/`: Pre-mutation rollback snapshots.
