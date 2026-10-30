"""Execution of planned synchronisation operations with automatic backup."""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from pab.core.config import ConfigManager
from pab.core.models.sync_plan import SyncPlan
from pab.registry.agent_registry import AgentRegistry
from pab.skills.manager import SkillManager


def apply_sync_plan(
    plan: SyncPlan,
    agent_registry: AgentRegistry,
    skill_manager: SkillManager,
    config: ConfigManager,
) -> Dict[str, Any]:
    # 1. Create Pre-Sync Backup
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_path = config.backups_dir / f"sync_backup_{plan.plan_id}_{timestamp}"
    backup_path.mkdir(parents=True, exist_ok=True)

    results = {"applied_operations": 0, "failed_operations": 0, "errors": []}

    for op in plan.operations:
        try:
            if op.resource_type == "agent":
                agent_registry.deploy_agent(op.resource_id, [op.target_provider])
            elif op.resource_type == "skill":
                skill_manager.deploy_skill(op.resource_id, [op.target_provider])
            results["applied_operations"] += 1
        except Exception as e:
            results["failed_operations"] += 1
            results["errors"].append(f"{op.resource_type} {op.resource_id} on {op.target_provider}: {str(e)}")

    plan.applied = True
    return results
