"""Converter between PersonaOS worker profiles (v1.yaml) and CanonicalAgentDefinition."""

from pathlib import Path
from typing import Any, Dict
import yaml

from pab.core.models.agent import (
    AgentCapabilities,
    AgentIdentity,
    AgentInstructions,
    AgentMemoryConfig,
    AgentPermissions,
    AgentPreferences,
    CanonicalAgentDefinition,
    ProviderConfig,
)


def convert_personaos_profile_to_canonical(
    profile_data: Dict[str, Any],
    profile_id: str,
) -> CanonicalAgentDefinition:
    """Convert PersonaOS worker profile dictionary to CanonicalAgentDefinition."""
    role = profile_data.get("role", profile_id)
    description = profile_data.get("description", f"PersonaOS Worker {role}")
    persona_data = profile_data.get("persona", {})

    style = f"{persona_data.get('style', 'professional')}, {persona_data.get('communication', 'concise')}"
    goals = persona_data.get("goals", [])
    objective = " | ".join(goals) if goals else f"Execute {role} duties reliably."

    skills = profile_data.get("skills", [])
    model = profile_data.get("model", "inherit")

    # Map permissions
    raw_perms = profile_data.get("permissions", [])
    fs_perm = "workspace"
    shell_perm = "approval_required" if any("deploy" in p or "write" in p for p in raw_perms) else "auto"

    providers: Dict[str, ProviderConfig] = {}
    runtime = profile_data.get("runtime", "openclaw")
    if runtime:
        providers[runtime] = ProviderConfig(enabled=True)

    definition = CanonicalAgentDefinition(
        id=profile_id,
        name=f"PersonaOS {role.capitalize()}",
        description=description,
        version=str(profile_data.get("version", "1.0.0")),
        identity=AgentIdentity(
            role=role.capitalize(),
            persona=f"Autonomy: {persona_data.get('autonomy', 'medium')}",
            objective=objective,
            avatar_emoji="🛠️" if "devops" in role.lower() else "🤖",
            style=style,
        ),
        instructions=AgentInstructions(
            system_prompt=profile_data.get("instructions", "").strip()
        ),
        capabilities=AgentCapabilities(
            skills=skills,
        ),
        preferences=AgentPreferences(
            model=model,
            response_style=persona_data.get("communication", "concise"),
        ),
        permissions=AgentPermissions(
            filesystem=fs_perm,
            shell_execution=shell_perm,
        ),
        providers=providers,
        metadata={"personaos_source": True, **profile_data.get("metadata", {})},
    )
    return definition


def load_personaos_profile(file_path: Path) -> CanonicalAgentDefinition:
    """Load PersonaOS profile file (e.g. v1.yaml) from disk."""
    data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    profile_id = file_path.parent.name
    return convert_personaos_profile_to_canonical(data, profile_id)
