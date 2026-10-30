"""Unit tests for Synchronisation and Reconciliation Engine."""

from pab.core.config import ConfigManager
from pab.core.models.agent import CanonicalAgentDefinition
from pab.registry.agent_registry import AgentRegistry
from pab.skills.manager import SkillManager
from pab.sync.engine import SyncEngine


def test_sync_plan_and_apply(config_mgr: ConfigManager, sample_agent_def: CanonicalAgentDefinition):
    engine = SyncEngine(config_mgr)

    # 1. Create a canonical agent and skill
    engine.agents.create_agent(sample_agent_def)
    engine.skills.create_skill(
        name="test-sync-skill",
        description="Skill created to verify reconciliation engine.",
    )

    # 2. Generate Plan
    plan = engine.plan(targets=["agy", "codex"])
    assert plan.plan_id.startswith("plan-")
    assert len(plan.operations) >= 2
    assert plan.approved is False
    assert plan.applied is False

    # 3. Apply Plan
    results = engine.apply(plan.plan_id)
    assert results["applied_operations"] >= 2
    assert results["failed_operations"] == 0

    # Verify plan state updated
    applied_plan = engine.get_plan(plan.plan_id)
    assert applied_plan is not None
    assert applied_plan.applied is True
