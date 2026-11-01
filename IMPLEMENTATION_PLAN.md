# PAB Pi Integration & Orchestration: Implementation Plan & Milestone Roadmap

## 1. Executive Summary & Review Gate

This document outlines the phased, reviewable implementation plan for integrating **Pi Coding Agent (`pi`)** and upgrading PAB into a **Universal Agent Control Plane** inspired by **Orca ADE CLI Orchestration**.

> [!IMPORTANT]
> **Review-First Rule**: In strict accordance with user instructions, no core PAB runtime modifications will be applied until this architectural design, specifications, ADRs, and conflict analysis have been reviewed and accepted.

---

## 2. Contract & Architecture Conflict Analysis

Prior to implementation, we conducted an exhaustive analysis of the existing PAB codebase (`src/pab/`), SQLite schemas (`pab.db`), and PersonaOS boundary contracts. The following conflicts and resolutions have been identified:

### 2.1 Conflict Matrix

| Conflict Area | Existing Codebase State | New Requirement | Conflict Severity | Resolution Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **CLI `pab run` Command** | `pab run` is a single Typer command accepting `agent_id` (`src/pab/cli/main.py:220`). | Standardized sub-app: `pab run create`, `pab run dispatch`, `pab run status`, `pab run results`. | **High** (Breaks legacy CLI parsing) | Convert `pab run` into a Typer sub-app (`run_app`). Preserve backward compatibility by adding `pab run agent <id>` and a root argument callback so `pab run <agent_id>` continues to work. |
| **Handoff Directory Layout** | `SwitchEngine` creates `.pab/handoffs/<id>/` (`src/pab/switch/engine.py:225`). | Canonical format v2 requires `.pab/sessions/handoffs/<id>/`. | **Medium** (Path mismatch across modules) | Adopt `.pab/sessions/handoffs/<id>/` as primary target. Add fallback symlink/lookup for `.pab/handoffs/<id>/` so older tools resolve cleanly. |
| **Orca Agent Inclusion** | Orca ADE supports native launch for `claude`, `codex`, `agy`, but **rejects `pi`**. | PAB must orchestrate Pi seamlessly within Orca workflows. | **High** (Runtime error if passed to Orca) | PAB implements a hybrid bridge: for Pi, PAB allocates an Orca worktree/terminal reference, launches Pi via `PiAgentAdapter` (RPC mode), and translates completion into Orca's Run mailbox (`worker_done`). |
| **Turn vs Settle Signals** | Generic adapters emit complete on process exit or initial response. | Pi emits `agent_end` per turn and `agent_settled` on final settle. | **Medium** (Premature completion bug) | `PiRpcClient` explicitly hooks `agent_settled`. PAB will never declare a Pi execution `COMPLETED` until `agent_settled` is received. |
| **PersonaOS Kernel Boundaries** | PersonaOS maintains authoritative worker profiles and task lifecycle. | PAB adds Run and Task coordination. | **Critical** (Risk of competing task schedulers) | Strictly enforce ADR 0005 & ADR 0007. PAB tasks map 1:1 to PersonaOS tasks (`personaos_task_id`). PAB handles execution attempts (Dispatches) only. |
| **Skills vs Extensions** | Existing `install_pi_skill` writes to `.pi/skills/`. | Pi also supports TypeScript extensions (`.pi/extensions/`). | **High** (Security & portability risk) | Keep Extensions in a distinct subsystem. Enforce that Open Agent Skills remain pure Markdown/scripts (`SKILL.md`). Block silent extension sync. |

---

## 3. Phased Implementation Roadmap

```mermaid
gantt
    title PAB Pi & Orchestration Roadmap
    dateFormat  YYYY-MM-DD
    section Core Pi Runtime
    Phase P0 : Pi Discovery & Capabilities :done, p0, 2026-11-01, 1d
    Phase P1 : PiAgentAdapter & RPC Client :active, p1, after p0, 2d
    Phase P2 : Canonical Handoff v2 (Claude->Pi, Codex->Pi) : p2, after p1, 2d
    section Skill & Workforce
    Phase P3 : Skill Synchronization & Immutability : p3, after p2, 1d
    Phase P4 : PersonaOS Worker Lease Preservation : p4, after p3, 1d
    section Orchestration Control
    Phase P5 : Orca Worktree & Terminal Bridge : p5, after p4, 2d
    Phase P6 : pab run Engine & Multi-Agent Reviews : p6, after p5, 2d
    Phase P7 : Pi Extension Security Management : p7, after p6, 1d
```

### Milestone P0: Pi CLI Discovery & Capability Registry
- **Deliverable**: Refined `src/pab/providers/pi/config.py` and `adapter.py` discovery methods.
- **Scope**:
  - Detect `pi` on `PATH`, `/usr/bin/pi`, `/usr/local/bin/pi`, and `~/.local/bin/pi`.
  - Capture installed version via `pi --version`.
  - Register capabilities in `ProviderRegistry` and `CapabilityRegistry`.
- **Acceptance Criteria**: `pab doctor` and `pab control list-agents --json` report Pi as detected, versioned, and healthy.

---

### Milestone P1: `PiAgentAdapter` & `PiRpcClient` Implementation
- **Deliverable**: `src/pab/providers/pi/rpc.py` and updated `src/pab/providers/pi/adapter.py`.
- **Scope**:
  - Implement `PiRpcClient` managing `subprocess.Popen(["pi", "--mode", "rpc", ...])`.
  - Binary line reader on stdout splitting strictly on LF (`\n`).
  - Thread-safe correlation map matching request IDs to command responses.
  - Event listener tracking `agent_start`, `message_update`, `tool_execution`, `agent_end`, and `agent_settled`.
  - Implement `PiAgentAdapter.launch()`, `prompt()`, `stop()`, `inspect()`, and `stream_events()`.
- **Acceptance Criteria**: Unit and mock tests demonstrate end-to-end command execution and proper settle event resolution.

---

### Milestone P2: Canonical Session Handoff v2 (Claude ➔ Pi & Codex ➔ Pi)
- **Deliverable**: Updated `src/pab/switch/engine.py`, `src/pab/sessions/handoff.py`, and `manager.py`.
- **Scope**:
  - Implement `.pab/sessions/handoffs/<id>/` structure (`manifest.json`, `summary.md`, `transcript.jsonl`, `context.json`, `source.json`).
  - Implement Pi session exporter reading `~/.pi/agent/sessions/*.jsonl`.
  - Implement handoff injection into Pi via `--append-system-prompt` or RPC prompt turn.
  - Ensure `source.session_id` and `destination.session_id` are distinctly recorded.
- **Acceptance Criteria**: Running `pab pi --from claude --dry-run` and live tests produce valid v2 bundles with cryptographic hashes and preserve conversation context.

---

### Milestone P3: Pi Skill Synchronization & Immutability Engine
- **Deliverable**: Updated `src/pab/providers/pi/skills.py` and `src/pab/skills/manager.py`.
- **Scope**:
  - Discover skills across `.pi/skills/`, `.agents/skills/`, and `~/.pi/agent/skills/`.
  - Validate frontmatter constraints (name ≤ 64 chars, description ≤ 1024 chars).
  - Guarantee canonical source immutability (canonical `SKILL.md` is strictly read-only).
- **Acceptance Criteria**: Deploying skills to Pi produces valid Open Agent Skills without altering source timestamps or hashes.

---

### Milestone P4: PersonaOS Worker Integration & Lease Integrity
- **Deliverable**: Updated `src/pab/personaos/bridge.py` and `profile_converter.py`.
- **Scope**:
  - Map PersonaOS worker profiles (`v1.yaml`) to Pi agent definitions (`~/.pi/agent/agents/<id>.json`).
  - Map worker memory references and tool privileges (`read`, `bash`, `edit`, `write`).
  - Preserve PersonaOS lease IDs and fence stale generation numbers.
- **Acceptance Criteria**: PersonaOS dev and qa workers cleanly import and configure Pi runtime profiles.

---

### Milestone P5: Orca Runtime Integration & Non-Native Bridge
- **Deliverable**: `src/pab/core/orca_bridge.py`.
- **Scope**:
  - Interface with Orca CLI (`orca-ide orchestration ...`).
  - Support native Orca dispatch for Claude/Codex/Antigravity.
  - Bridge Pi by allocating an Orca worktree/terminal and sending Orca `heartbeat`, `status`, and `worker_done` messages upon Pi `agent_settled`.
- **Acceptance Criteria**: Orchestrated task dispatches to Pi properly settle Orca's Run mailbox.

---

### Milestone P6: Multi-Agent Orchestration & Decision Gates (`pab run`)
- **Deliverable**: `src/pab/cli/run.py` and `src/pab/core/orchestration_engine.py`.
- **Scope**:
  - Implement `pab run create`, `pab run dispatch`, `pab run status`, `pab run results`.
  - Implement `DecisionGate` creation and interactive resolution (`pab run gate`).
  - Implement multi-reviewer fan-out with isolated read-only worktrees.
  - Implement result aggregation synthesizing outputs from Codex, Claude, and Pi.
- **Acceptance Criteria**: Automated test reproduces Use Case C (three agents independently reviewing a git commit and outputting a consolidated report).

---

### Milestone P7: Pi Extension Security & Isolation Management
- **Deliverable**: `src/pab/providers/pi/extensions.py`.
- **Scope**:
  - Discover TypeScript extensions in `.pi/extensions/` and `~/.pi/agent/extensions/`.
  - Provide inspection commands (`pab agent inspect pi --extensions`).
  - Perform static safety verification to protect against prompt injection and secret leakage.
- **Acceptance Criteria**: Extensions are cleanly separated from skills and audited before use.
