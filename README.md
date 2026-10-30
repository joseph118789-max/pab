# PersonaOS Agent Bridge (PAB)

> One management layer. Four agent platforms. One shared knowledge base.

PersonaOS Agent Bridge (PAB) is a universal control plane for managing AI agents across:
- **OpenClaw**
- **Google Antigravity CLI (`agy`)**
- **OpenAI Codex CLI**
- **Anthropic Claude Code**

## Quick Start

```bash
# Doctor check
pab doctor

# List provider capabilities
pab providers list
pab providers capabilities

# List canonical agents
pab agent list

# Create a new canonical agent
pab agent create devops-engineer

# Deploy to all providers
pab agent deploy devops-engineer --to all

# Universal skill management
pab skill list
pab skill validate <skill-name>
pab skill deploy <skill-name> --to all

# Shared memory hub
pab memory list
pab memory search "database"

# Cross-platform session handoff
pab session handoff --from codex --to agy --session <session-id>
```
