# ADR 0007: Orca Orchestration Runtime Boundary and Control Plane Coexistence

## Status
Proposed (Accepted in Design Specification)

## Context
Orca Application Development Environment (ADE) introduces an orchestration architecture centered around:
- **Runs**: Scoped execution namespaces and coordinator mailboxes.
- **Tasks**: Units of work with dependency graphs (DAGs).
- **Dispatches**: Execution attempts bound to specific agent runtimes and terminals.
- **Messages**: Threaded inter-agent and coordinator-worker communication (`ask`, `reply`, `worker_done`, `heartbeat`).
- **Decision Gates**: Human-in-the-loop approval gates that block tasks until resolved.
- **Terminals & Worktrees**: Isolated Git worktree workspaces and pseudo-terminals for agent execution.

At the same time, **PersonaOS** is the authoritative kernel owning worker identity, persistent memory, task claiming, and worker leases.

If PAB attempted to build its own independent task queue or workforce scheduler, it would directly conflict with the PersonaOS kernel. Furthermore, Orca's built-in supervised-worker agent registry currently supports agents such as Claude, Codex, Cursor, and Antigravity, but does **not** natively include Pi.

## Decision
We establish a strict, non-competing three-tier architectural boundary:
1. **PersonaOS Kernel (Authoritative Task & Workforce Authority)**:
   - Owns Worker Identity (`v1.yaml`), capabilities, persistent memory, task queues, lease management, and final task lifecycle transitions (`PENDING`, `CLAIMED`, `COMPLETED`, `FAILED`).
   - PAB will **never** implement an alternative task queue or worker lease manager.

2. **Orca ADE (Placement, Worktree & Terminal Environment)**:
   - Owns Git worktrees, terminal virtualization (`term_orca_*`), remote execution servers, and IDE interface integration.
   - For native Orca agents (Claude, Codex, Antigravity), PAB coordinates through Orca CLI orchestration (`orca orchestration worker-start`).

3. **PAB Universal Agent Control Plane (Cross-Agent Interoperability & Supervision)**:
   - Acts as the universal coordinator and execution bridge.
   - For agents supported by Orca, PAB delegates process launching to Orca terminals.
   - For Pi (which is not natively supported by Orca's `worker-start`), PAB operates a hybrid bridge: PAB obtains an Orca worktree/terminal reference or managed process handle, launches Pi via `PiAgentAdapter` (RPC mode), and translates Pi's execution events into Orca orchestration messages (`heartbeat`, `status`, `worker_done`).
   - PAB standardizes orchestration CLI commands (`pab run create`, `pab run dispatch`, `pab run status`, `pab run results`) that map transparently to either Orca or standalone multi-agent execution.

## Consequences
### Positive
- Strict adherence to separation of concerns: Zero duplication of PersonaOS task lifecycle.
- Full compatibility with Orca's Worktree and Terminal isolation.
- Extends multi-agent orchestration to Pi immediately without waiting for upstream Orca native agent inclusion.
- Supports heterogeneous review and development workflows (e.g., Claude writes spec, Codex writes code, Pi conducts independent review).

### Negative / Trade-offs
- PAB must maintain translation logic between Pi RPC events and Orca orchestration message types.
- Requires PAB to manage terminal handles and lifecycle fencing when bridging non-native agents into Orca.
