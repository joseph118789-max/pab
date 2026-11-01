# ADR 0006: Pi Agent Runtime Integration via Subprocess Bidirectional JSONL RPC

## Status
Proposed (Accepted in Design Specification)

## Context
PersonaOS Agent Bridge (PAB) is extending support to Pi (`pi`), a modern autonomous coding assistant capable of multi-turn code reasoning, file editing, and command execution. Pi offers multiple integration interfaces:
1. **Interactive TUI**: Designed for human interaction on a TTY terminal.
2. **Print Mode (`pi -p <prompt>`)**: One-shot batch execution that runs a single prompt to completion and exits.
3. **JSON Mode (`pi --mode json`)**: Emits structured JSON events to stdout for a single prompt or batch.
4. **RPC Mode (`pi --mode rpc`)**: Starts a persistent, long-running child process controlled through strict JSONL records on stdin/stdout, with asynchronous command handling, request/response correlation, and fine-grained event streaming.
5. **TypeScript SDK**: Direct programmatic embedding for Node.js / Bun environments.

Because PAB is a Python-based universal agent control plane managing supervised multi-turn tasks, long-running worker leases, interactive steering, and event-driven monitoring, a one-shot execution model (Print mode) is inadequate for interactive supervision and requires tearing down/restarting the runtime context repeatedly. Conversely, the TypeScript SDK would require embedding Node.js runtimes within Python processes or running an external Node gateway.

## Decision
PAB adopts **Pi RPC Mode (`pi --mode rpc`)** as the primary supervised execution interface:
1. PAB launches `pi --mode rpc` as a managed subprocess using `subprocess.Popen` with unbuffered binary pipes on stdin/stdout.
2. Command framing is strictly JSONL (single JSON object terminated by LF `\n`).
3. Every command carries an idempotent request `id` (UUIDv4) that is matched against incoming responses (`type: "response"`).
4. An asynchronous reader thread continuously consumes stdout, multiplexing responses to awaiting command futures and streaming session events to registered PAB event listeners.
5. Work completion is determined by the `agent_settled` event rather than `agent_end`, ensuring that follow-ups, auto-compaction, and auto-retries have completely terminated.
6. Interactive CLI mode (`pab pi`) remains supported for human operator attachment, delegating to the native `pi` executable in the project workspace.

## Consequences
### Positive
- Full lifecycle control: PAB can prompt, steer, abort, switch models, and inspect internal tokens/messages without restarting the process.
- Low latency: Persistent process avoids cold start overhead of Node/model initialization.
- Real-time observability: Turn-by-turn text deltas, tool executions, and status updates are piped into PAB's execution supervisor.
- Language independence: No Node.js runtime bridging required in Python.

### Negative / Trade-offs
- Requires robust subprocess lifecycle handling (SIGTERM, SIGKILL timeouts, pipe buffer deadlock prevention).
- Client must respond to or safely ignore `extension_ui_request` protocol messages (e.g. title updates, dialog notifications).
