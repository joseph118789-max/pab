# Provider Capability Matrix

| Feature | OpenClaw | Google Antigravity (`agy`) | OpenAI Codex CLI | Anthropic Claude Code |
| :--- | :--- | :--- | :--- | :--- |
| **Installed Binary** | `openclaw` | `agy` | `codex` | `claude` |
| **Agent Config Format** | JSON (`openclaw.json`) + Workspace | Markdown + YAML Frontmatter (`agent.md`) | TOML (`~/.codex/agents/*.toml`) | Markdown + Frontmatter (`~/.claude/agents/*.md`) |
| **Agent Workspace** | Dedicated directory per agent | Project `.agents/` or Global | Working dir / Sandbox | Working dir / Project |
| **Primary Instructions**| `AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `USER.md` | `GEMINI.md`, `AGENTS.md`, `.agents/rules/*.md` | `AGENTS.md`, `.codex/instructions.md` | `CLAUDE.md`, `AGENTS.md` |
| **Skill System** | `SKILL.md` + plugins | `SKILL.md` + Progressive Disclosure | `SKILL.md` + system skills | `SKILL.md` / subagent tools |
| **Skill Locations** | `~/.openclaw/agents/<id>/skills/` | `~/.gemini/config/skills/`, `.agents/skills/` | `~/.codex/skills/`, `.agents/skills/` | `~/.claude/skills/`, `.claude/skills/` |
| **Memory System** | `MEMORY.md`, `memory/*.md`, `lcm.db` | Brain transcripts, artifacts, rules | `memories_1.sqlite`, Markdown files | Project memories, Markdown context |
| **Session Tracking** | `sessions/*.json`, SQLite | `brain/<conv_id>/transcript.jsonl` | `logs_2.sqlite`, JSON lines | Session JSON files |
| **Native Resume** | `openclaw run <id>` | `agy --conversation <id>` | `codex resume <id>` | `claude resume <id>` |
| **Cross-Platform Handoff**| Portable Handoff Bundle | Portable Handoff Bundle | Portable Handoff Bundle | Portable Handoff Bundle |
| **Execution Sandbox** | Bubblewrap / container isolation | Terminal sandbox (`--sandbox`) | Docker / restricted terminal | System permissions |
