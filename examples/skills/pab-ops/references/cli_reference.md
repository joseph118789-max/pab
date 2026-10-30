# PersonaOS Agent Bridge (PAB) CLI Reference

Complete quick reference for all CLI subcommands in PAB.

## 1. System & Providers
- `pab doctor` — Run comprehensive environment diagnostics across all 4 platforms and SQLite database.
- `pab providers list` — List detected providers, versions, and capability matrices.
- `pab providers detect <name>` — Run deep inspection of a specific provider.

## 2. Agent Registry
- `pab agent list` — List all canonical agent definitions.
- `pab agent show <agent_id>` — Display full YAML specification, identity, instructions, skills, preferences, and provider status.
- `pab agent import <agent_id> --from <openclaw|agy|codex|claude>` — Import an existing native agent into canonical registry.
- `pab agent deploy <agent_id> --to <openclaw,agy,codex,claude|all>` — Compile and deploy canonical agent to native platform configs.
- `pab agent clone <source_id> <new_id> [--name <name>]` — Fork an agent with independent version history.
- `pab agent diff <agent_id> --version1 <v1> --version2 <v2>` — Compare configuration diffs across versions.
- `pab agent rollback <agent_id> <version>` — Revert agent configuration to a previous snapshot.

## 3. Skill Manager
- `pab skill list` — List all skills in canonical library.
- `pab skill create <name> --desc <description>` — Scaffold a new Open Agent Skill directory.
- `pab skill validate <name>` — Validate skill against Open Agent Skills specification.
- `pab skill audit <name>` — Security scan for dangerous commands, shell injection, or credential leaks.
- `pab skill deploy <name> --to <target|all>` — Deploy skill to provider global and workspace directories.
- `pab skill sync [--to all]` — Synchronise entire skill library across platforms.
- `pab skill import <path>` — Ingest local skill directory into canonical library.
- `pab skill export <name> --to <path>` — Export portable skill folder.

## 4. Memory Hub
- `pab memory search "<query>" [--scope <global|project|agent>]` — Query indexed memories with snippet highlights.
- `pab memory list [--scope <scope>]` — List indexed memories in SQLite.
- `pab memory import <openclaw|agy|codex|claude>` — Ingest native memories with provenance tagging (`untrusted: true`).
- `pab memory add <content> --scope <global|project|agent> [--agent-id <id>]` — Add shared memory note.

## 5. Session & Cross-Platform Handoff
- `pab session list` — Discover active conversations across platforms.
- `pab session handoff --from <provider> <session_id>` — Export portable `HANDOFF.md` + `context.json` bundle.
- `pab session resume <provider> <session_id>` — Resume same-provider session natively (if supported).

## 6. Execution Runner
- `pab run <agent_id> --provider <openclaw|agy|codex|claude> [--with-handoff <session_id>]` — Validate pre-flight readiness and launch agent.

## 7. Backups
- `pab backup create` — Create full snapshot of `~/.pab/` and SQLite state.
- `pab backup list` — List available recovery snapshots.
- `pab backup restore <backup_id>` — Restore configuration state.
