# PAB Session Interoperability & Handoff Specification (Version 2.0)

## 1. Executive Summary

This document specifies the **Canonical Session Handoff Format (v2.0)** for the **PersonaOS Agent Bridge (PAB)**. 

Moving work between diverse AI coding agents (such as Anthropic Claude Code, OpenAI Codex, Google Antigravity, OpenClaw, and Pi) requires capturing conversational context, code diffs, architectural decisions, and PersonaOS worker identities in a platform-agnostic structure. This specification defines the storage layout, data contracts, normalization procedures, and security controls that govern cross-agent session migrations.

---

## 2. Session Integrity Principles

1. **Strict Tier Distinction**:
   - **Tier 1 (Native Resume)**: Only permitted when the source and destination runtimes are identical and the provider natively supports resuming session state (e.g., `pi --continue`, `claude --resume`).
   - **Tier 2 (Portable Handoff Migration)**: Used whenever transitioning across different agent platforms.
2. **Session ID Integrity Rule**:
   - PAB will **never** pretend that a source agent's session ID is valid in a destination runtime.
   - Cross-agent handoffs initialize a **new native session** in the target provider. PAB explicitly maps and records both `source.session_id` and `destination.session_id`.
3. **Secret Redaction by Default**:
   - All exported transcripts, diffs, and context files pass through PAB's cryptographic entropy and regex scanner (`redact_secrets()`) before writing to disk.

---

## 3. Storage Hierarchy

The versioned canonical PAB workspace directory is organized as follows:

```text
.pab/
├── agents/
│   ├── registry.yaml                       # Local registry snapshot
│   └── capabilities/                       # Agent runtime capability descriptors
│       ├── pi.yaml
│       ├── codex.yaml
│       ├── claude.yaml
│       └── agy.yaml
├── sessions/
│   ├── exports/                            # Raw provider-exported normalized sessions
│   └── handoffs/                           # Portable Handoff Bundles (v2.0)
│       └── <handoff-id>/
│           ├── manifest.json               # Canonical metadata & provenance
│           ├── summary.md                  # High-signal LLM briefing document
│           ├── transcript.jsonl            # Normalized conversation history
│           ├── context.json                # Structured task & decision state
│           ├── source.json                 # Unaltered source snapshot
│           └── workspace.diff              # Git status & uncommitted diffs
├── skills/
│   ├── canonical/                          # Canonical Open Agent Skills
│   ├── adapters/                           # Provider-specific generated wrappers
│   │   ├── pi/
│   │   ├── codex/
│   │   └── claude/
│   └── mappings.yaml                       # Skill resolution mapping
├── workspaces/                             # Worktree tracking metadata
└── runs/                                   # Orchestration run state
```

---

## 4. Canonical Handoff Bundle Schema (`manifest.json`)

The `manifest.json` file is the cryptographically verified entry point of every handoff bundle:

```json
{
  "$schema": "https://pab.personaos.dev/schemas/handoff-manifest-v2.json",
  "version": "2.0",
  "handoff_id": "handoff-claude-to-pi-20261101-104500",
  "source": {
    "provider": "claude",
    "agent_id": "architect-claude",
    "session_id": "sess_01J8K3M9XYZ"
  },
  "destination": {
    "provider": "pi",
    "agent_id": "reviewer-pi",
    "session_id": "pi:new"
  },
  "workspace": {
    "project_path": "/root/.openclaw/workspace/projects/pab",
    "git_branch": "main",
    "head_commit": "c40c6fb23180822d5b81b571b84458928711e97b",
    "is_dirty": true,
    "modified_files": [
      "src/pab/providers/pi/adapter.py"
    ]
  },
  "worker_identity": {
    "worker_id": "personaos-developer",
    "profile_version": "1.2.0",
    "role": "Autonomous Senior Systems Engineer",
    "lease_id": "lease-9831a"
  },
  "context": {
    "original_objective": "Implement Pi Agent RPC adapter and Orca orchestration",
    "task_summary": "Completed initial scaffolding for Pi config and sessions; beginning RPC client implementation",
    "skills": [
      "pab-ops",
      "orchestration",
      "python"
    ],
    "technical_decisions": [
      "Use pi --mode rpc instead of one-shot print mode for bidirectional control",
      "Adopt agent_settled event to fence turn completion"
    ],
    "unresolved_issues": [
      "Pi does not exist in Orca native agent registry; requires PAB bridge"
    ],
    "next_steps": [
      "Validate Pi RPC client over mock subprocess",
      "Implement pab run command suite"
    ]
  },
  "provenance": {
    "created_at": "2026-11-01T10:45:00Z",
    "pab_version": "1.0.0",
    "bundle_hashes": {
      "summary.md": "sha256:7e8a9...",
      "transcript.jsonl": "sha256:4b2c1...",
      "context.json": "sha256:1a9f3...",
      "source.json": "sha256:9d3e8...",
      "workspace.diff": "sha256:e3b0c..."
    }
  }
}
```

---

## 5. Normalized Transcript Specification (`transcript.jsonl`)

Regardless of whether the source is Claude, Codex, or Pi, the transcript is normalized into strict JSON Lines where each line is a `TranscriptEntry`:

```json
{"sequence": 1, "timestamp": "2026-11-01T10:30:00Z", "role": "user", "content": "Analyze the codebase for Pi integration points"}
{"sequence": 2, "timestamp": "2026-11-01T10:30:15Z", "role": "assistant", "content": "I will examine the providers directory.", "tool_calls": [{"id": "call-1", "name": "read", "arguments": {"path": "src/pab/providers/pi/adapter.py"}}]}
{"sequence": 3, "timestamp": "2026-11-01T10:30:20Z", "role": "tool_result", "tool_call_id": "call-1", "content": "class PiAdapter(AgentAdapter): ..."}
{"sequence": 4, "timestamp": "2026-11-01T10:31:00Z", "role": "assistant", "content": "The PiAdapter requires full RPC streaming support."}
```

### Supported Entry Roles:
- `system`: Context, instructions, or environment declarations.
- `user`: Human prompts or coordinator task dispatches.
- `assistant`: Model thoughts and responses.
- `tool_call`: Structured tool invocation details.
- `tool_result`: Tool execution stdout/stderr and exit code.

---

## 6. Provider Session Extraction Logic

### 6.1 Pi Session Extractor
Pi stores sessions as JSONL conversation trees in:
- System: `~/.pi/agent/sessions/<project-dir-slug>/*.jsonl`
- Project: `<workspace>/.pi/sessions/*.jsonl` (when `--session-dir` is active)

The PAB extractor:
1. Locates session files matching the project slug or exact session UUID.
2. Traverses parent-child message tree nodes from root prompt to leaf turn.
3. Filters internal model metadata while preserving tool inputs/outputs.
4. Generates `NormalizedSession` instance.

### 6.2 Claude Code Session Extractor
Claude Code stores history in:
- `~/.claude/projects/<project-slug>/sessions/*.json` or SQLite logs.

The PAB extractor extracts:
1. User prompt requests.
2. Assistant replies and tool execution transcripts (`Bash`, `FileEdit`, `Glob`).
3. Synthesizes `completed_work` and `pending_work` from final assistant messages.

---

## 7. Context Injection into Destination Agents

When resuming in the target provider, PAB formats the handoff bundle for optimal comprehension:

### 7.1 Injection into Pi
When launching Pi after a handoff:
```bash
pi --append-system-prompt ".pab/sessions/handoffs/<id>/summary.md" \
   -p "You are continuing work transferred from Claude Code. Read .pab/sessions/handoffs/<id>/summary.md and continue the outstanding task."
```
For RPC mode, PAB initializes the session with:
```json
{
  "id": "init-handoff-1",
  "type": "prompt",
  "message": "Continuing work from handoff <id>. Review summary and current repository state before acting."
}
```

### 7.2 Injection into Claude Code
```bash
claude -p "Review .pab/sessions/handoffs/<id>/summary.md and resume development."
```

### 7.3 Injection into OpenAI Codex
```bash
codex "Continue task outlined in .pab/sessions/handoffs/<id>/summary.md"
```
