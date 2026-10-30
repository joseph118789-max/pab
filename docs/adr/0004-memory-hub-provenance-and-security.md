# ADR 0004: Memory Hub Provenance, Deduplication, and Security Isolation

## Status
Accepted

## Context
Aggregating memory from diverse AI agents carries risks of duplicate notes, stale advice, and prompt injection attacks embedded in imported logs.

## Decision
1. The PAB Memory Hub classifies memories into clear tiers: User, Global, Project, Agent, Daily, Imported, and Handoff.
2. Imported memories are cryptographically hashed (SHA-256) for deduplication, attributed with source and timestamp, and flagged as `untrusted` until reviewed by an administrator.
3. Content is never automatically treated as authoritative system instructions.

## Consequences
- Safe cross-agent memory sharing.
- Prevention of circular prompt injections or malicious instruction overrides.
