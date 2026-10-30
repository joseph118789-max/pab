# ADR 0001: Separation of Canonical Registry from Native Runtimes

## Status
Accepted

## Context
Each AI agent provider (OpenClaw, Antigravity, Codex, Claude Code) utilizes different configuration structures, schema conventions, and storage mechanisms. Attempting to force all providers into a single rigid runtime causes fragility and breaks vendor-specific capabilities.

## Decision
PAB acts as a canonical management layer and single source of truth. It stores canonical YAML agent profiles, and delegates deployment to specialized provider adapters that compile and synchronize native configuration files (`openclaw.json`, `agent.md`, `.toml`, subagent `.md`).

## Consequences
- Native features not mapped in the canonical schema are safely preserved under provider-specific extension blocks.
- PAB can manage agents across all four platforms without modifying vendor CLI internals.
