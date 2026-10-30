# ADR 0002: Open Agent Skills as the Canonical Standard

## Status
Accepted

## Context
Reusability of agent capabilities across platforms requires an open, portable skill format. Vendor-specific skill mechanisms (such as proprietary tool manifests or code snippets) are hard to migrate.

## Decision
Adopt the Open Agent Skills specification (`SKILL.md` with YAML frontmatter `name`, `description`, `metadata`, accompanied by `scripts/`, `references/`, and `assets/`) as PAB's canonical skill representation.

## Consequences
- Canonical skills remain completely untouched during sync.
- Provider adapters generate provider-specific wrapper configs (such as Codex TOML tool entries or Claude tool manifests) pointing to the canonical assets.
