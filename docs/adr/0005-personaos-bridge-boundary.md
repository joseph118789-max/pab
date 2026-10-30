# ADR 0005: PersonaOS Integration Boundaries

## Status
Accepted

## Context
PersonaOS contains an execution kernel, worker lease system, and task queue. PAB should enhance PersonaOS without competing with its kernel.

## Decision
PAB acts as an external agent management and skill synchronization layer for PersonaOS. PAB reads PersonaOS worker profiles (`v1.yaml`), maps them into canonical agent definitions, provisions required skills and instructions across external providers, and reports provider availability and health.

## Consequences
- PAB does not implement task claiming, worker leases, or competing schedulers.
- PersonaOS kernel retains complete authority over task lifecycles.
