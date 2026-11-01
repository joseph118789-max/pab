# ADR 0008: Canonical Handoff Package v2 and Session Identity Integrity

## Status
Proposed (Accepted in Design Specification)

## Context
When migrating work between heterogeneous AI agents (e.g., Claude Code ➔ Pi, or Codex ➔ Claude), agents maintain proprietary internal state:
- Token-level KV caches and session databases are incompatible across providers.
- Session IDs (UUIDs or project-scoped identifiers) are native to each runtime; presenting a Claude session ID as a Pi session ID causes runtime errors or silent corruption.
- Context handoff requires migrating conversational history, git state, unresolved decisions, active skills, and PersonaOS worker identity references into an auditable, portable bundle.

Existing PAB implementations used an ad-hoc `.pab/handoffs/<id>` folder with loose markdown files. A standardized, versioned layout is required for reliable control plane operations.

## Decision
1. **Canonical Handoff Format v2**:
   All cross-agent transfers will emit a versioned directory structure:
   ```text
   .pab/
   ├── agents/
   │   ├── registry.yaml
   │   └── capabilities/
   │       ├── pi.yaml
   │       ├── codex.yaml
   │       └── claude.yaml
   ├── sessions/
   │   └── handoffs/
   │       └── <handoff-id>/
   │           ├── manifest.json
   │           ├── summary.md
   │           ├── transcript.jsonl
   │           ├── context.json
   │           └── source.json
   ├── skills/
   │   ├── canonical/
   │   ├── adapters/
   │   │   ├── pi/
   │   │   ├── codex/
   │   │   └── claude/
   │   └── mappings.yaml
   ├── workspaces/
   └── runs/
   ```

2. **Session Identity Integrity**:
   - PAB will **never** pretend that a source agent's session ID is valid in the destination agent runtime.
   - Cross-agent transfers initialize a brand new native session on the destination provider, injecting the handoff context via the runtime's supported initialization mechanism (prompt, system prompt append, or initial turn).
   - Both `source.session_id` and `destination.session_id` are explicitly captured in `manifest.json` with cryptographic provenance hashes.
   - Native resume (Tier 1) remains strictly restricted to intra-provider sessions (`source_provider == destination_provider`).

## Consequences
### Positive
- Total prevention of corrupted session databases or invalid CLI session lookups.
- Auditable trail of custody for every migration (who transferred what, when, commit SHA, and artifact hashes).
- Destination agents receive structured, high-signal task summaries and diffs rather than messy raw prompt dumps.

### Negative / Trade-offs
- The destination agent does not retain exact token cache state and must parse the handoff summary on its first turn.
- Additional disk storage in `.pab/sessions/handoffs/` for full transcripts and manifests.
