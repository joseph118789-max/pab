# ADR 0009: Open Agent Skills Synchronization and Pi Extension Isolation

## Status
Proposed (Accepted in Design Specification)

## Context
Pi supports two distinct extension mechanisms:
1. **Agent Skills**: Open Agent Skills specification (`SKILL.md` with YAML frontmatter) located in `.pi/skills/`, `.agents/skills/`, or `~/.agents/skills/`. Skills contain natural language instructions, scripts, assets, and references. They are declarative and portable across all PAB-supported agents.
2. **Extensions**: TypeScript modules (e.g., `extensions/*.ts`) loaded via `jiti` that execute arbitrary Node.js code within the Pi process, registering custom tools, custom CLI commands, and event handlers (`before_agent_start`, `agent_settled`).

Treating Pi extensions as generic skills would break cross-agent portability (as Claude, Codex, or agy cannot execute arbitrary Pi TypeScript extension code) and create severe security risks (unvetted remote code execution).

Furthermore, when synchronizing skills across platforms, source skills must never be mutated or overwritten in-place.

## Decision
1. **Immutable Canonical Skills**:
   - PAB retains canonical Open Agent Skills in `.pab/skills/canonical/<skill-name>/`.
   - Synchronization to Pi copies or maps skills into Pi's recognized skill directories:
     - Project-local: `<workspace>/.pi/skills/<skill-name>/` or `<workspace>/.agents/skills/<skill-name>/`
     - Global: `~/.pi/agent/skills/<skill-name>/` or `~/.agents/skills/<skill-name>/`
   - Source canonical files are strictly read-only during compilation and synchronization.

2. **Strict Separation of Extensions from Skills**:
   - Pi extensions are managed as a separate, distinct subsystem: **Extension Management**.
   - Extensions reside in `.pi/extensions/` or user `~/.pi/agent/extensions/`.
   - PAB will not attempt to convert TypeScript extensions into Open Agent Skills or deploy them to non-Pi platforms.
   - PAB will provide separate CLI commands (`pab agent inspect pi --extensions`, `pab skill validate pi`) and perform static safety audits on extensions before execution.

## Consequences
### Positive
- Prevents cross-platform skill corruption.
- Preserves security boundaries by preventing arbitrary TypeScript execution under the guise of Markdown skills.
- Maintains compliance with the standard Open Agent Skills specification across OpenClaw, agy, Claude, Codex, and Pi.

### Negative / Trade-offs
- Pi-specific extensions cannot be shared directly with other agent platforms without manual tool rewriting (e.g., translating an extension tool into an MCP server or Codex tool).
