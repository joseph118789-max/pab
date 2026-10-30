# ADR 0003: Two-Tier Session Migration Strategy

## Status
Accepted

## Context
Resuming a runtime conversation across platforms (e.g., executing a raw Codex checkpoint inside Claude Code or Antigravity) is impossible due to proprietary token contexts, internal KV-caches, and differing tool schemas.

## Decision
PAB implements a two-tier session management model:
1. **Tier 1 (Native Resume):** Enabled only when the source and destination provider are identical and the provider CLI officially supports resume (e.g. `agy --conversation`, `openclaw run`).
2. **Tier 2 (Cross-Platform Portable Handoff Bundle):** PAB exports and normalizes session data into a structured handoff package consisting of `HANDOFF.md`, `context.json` (task summary, objective, decisions, files, errors, next steps), `transcript_excerpt.jsonl`, and `workspace.diff`. This handoff context is then injected into the target provider's workspace.

## Consequences
- No corruption of provider session databases.
- Reliable cross-platform continuation without losing context.
