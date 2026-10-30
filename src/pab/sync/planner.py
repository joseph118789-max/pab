"""Reconciliation plan generation for agents and skills."""

import uuid
from typing import List
from pab.core.models.sync_plan import PlannedOperation, SyncPlan
from pab.registry.agent_registry import AgentRegistry
from pab.skills.manager import SkillManager


def generate_sync_plan(
    agent_registry: AgentRegistry,
    skill_manager: SkillManager,
    targets: List[str],
) -> SyncPlan:
    plan_id = f"plan-{uuid.uuid4().hex[:8]}"
    operations: List[PlannedOperation] = []
    conflicts: List[str] = []

    all_providers = (
        list(agent_registry.providers._providers.keys())
        if "all" in targets
        else targets
    )

    # 1. Plan Agent synchronisation
    canonical_agents = agent_registry.list_agents()
    for profile in canonical_agents:
        agent = profile.agent
        for p_name in all_providers:
            provider = agent_registry.providers.get(p_name)
            if not provider:
                continue

            existing = provider.get_agent(agent.id)
            if existing is None:
                operations.append(
                    PlannedOperation(
                        resource_type="agent",
                        resource_id=agent.id,
                        target_provider=p_name,
                        action="create",
                        target_path=existing.get("path") if existing else f"{p_name}://agents/{agent.id}",
                        description=f"Deploy canonical agent '{agent.id}' ({agent.name}) to {p_name}",
                    )
                )
            else:
                operations.append(
                    PlannedOperation(
                        resource_type="agent",
                        resource_id=agent.id,
                        target_provider=p_name,
                        action="update",
                        target_path=existing.get("path") or f"{p_name}://agents/{agent.id}",
                        description=f"Synchronize agent '{agent.id}' updates to {p_name}",
                    )
                )

    # 2. Plan Skill synchronisation
    canonical_skills = skill_manager.list_skills()
    for skill in canonical_skills:
        for p_name in all_providers:
            provider = skill_manager.providers.get(p_name)
            if not provider:
                continue

            skills_list = provider.list_skills()
            exists = any(s["name"] == skill.manifest.name for s in skills_list)
            action = "update" if exists else "create"

            operations.append(
                PlannedOperation(
                    resource_type="skill",
                    resource_id=skill.manifest.name,
                    target_provider=p_name,
                    action=action,
                    target_path=f"{p_name}://skills/{skill.manifest.name}",
                    description=f"{action.capitalize()} skill '{skill.manifest.name}' on {p_name}",
                )
            )

    return SyncPlan(
        plan_id=plan_id,
        targets=all_providers,
        operations=operations,
        conflicts=conflicts,
    )
