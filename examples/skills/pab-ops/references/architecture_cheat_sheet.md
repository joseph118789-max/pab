# PAB Architecture Cheat Sheet

## Core Concept
PAB owns canonical agent definitions, skill packages, memory index, and handoff bundles. Platform adapters compile canonical definitions into native platform formats.

```
+-------------------------------------------------------------+
|                 PersonaOS Agent Bridge (PAB)                |
|  Canonical Profiles | Skill Library | Memory Hub | Handoffs |
+-------------------------------------------------------------+
          |                 |               |            |
          v                 v               v            v
      OpenClaw          Antigravity       Codex        Claude
   (openclaw.json)     (.agents/agent.md) (TOML)    (Markdown)
```

## Platform Target Paths

| Resource | OpenClaw | Antigravity (`agy`) | OpenAI Codex | Anthropic Claude Code |
| :--- | :--- | :--- | :--- | :--- |
| **Agent Profile** | `openclaw.json` + `~/.openclaw/agents/<id>/` | `.agents/agents/<id>/agent.md` | `~/.codex/agents/<id>.toml` | `~/.claude/agents/<id>.md` |
| **Workspace Skills** | `~/.openclaw/workspace/skills/<id>/` | `.agents/skills/<id>/` | `.agents/skills/<id>/` | `.claude/skills/<id>/` |
| **Global Skills** | `~/.openclaw/plugin-skills/<id>/` | `~/.gemini/config/skills/<id>/` | `~/.codex/skills/<id>/` | `~/.claude/skills/<id>/` |
| **Instructions** | `AGENTS.md`, `SOUL.md`, `USER.md` | `GEMINI.md`, `AGENTS.md` | `AGENTS.md` | `CLAUDE.md` |
| **Sessions** | `~/.openclaw/agents/<id>/sessions/` | `~/.gemini/antigravity-cli/brain/*/` | `~/.codex/sessions.db` | `~/.claude/sessions/` |

## Security Rules
1. Never hardcode live API keys, credentials, or secrets in agent profiles or skills.
2. Imported memories are quarantined with `untrusted: true` provenance.
3. Native resumption is strictly prohibited across different platforms; cross-platform transitions MUST use portable handoff bundles (`HANDOFF.md` + `context.json`).
