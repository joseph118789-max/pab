"""Central Synchronisation and Reconciliation Engine."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.config import ConfigManager
from pab.core.db import Database
from pab.core.exceptions import SyncConflictError
from pab.core.models.sync_plan import SyncPlan
from pab.registry.agent_registry import AgentRegistry
from pab.skills.manager import SkillManager
from pab.sync.applier import apply_sync_plan
from pab.sync.planner import generate_sync_plan


class SyncEngine:
    """Orchestrates plan generation, diff inspection, backups, and atomic application."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config = config_manager or ConfigManager()
        self.db = Database(self.config.db_path)
        self.agents = AgentRegistry(self.config)
        self.skills = SkillManager(self.config)

    def plan(self, targets: List[str]) -> SyncPlan:
        plan = generate_sync_plan(self.agents, self.skills, targets)
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sync_plans (plan_id, created_at, approved, applied, plan_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    plan.plan_id,
                    plan.created_at,
                    1 if plan.approved else 0,
                    1 if plan.applied else 0,
                    json.dumps(plan.model_dump(mode="json")),
                ),
            )
            conn.commit()

        self.db.record_audit(
            event_type="create_sync_plan",
            resource_type="sync_plan",
            resource_id=plan.plan_id,
            details={"operations": len(plan.operations), "targets": plan.targets},
        )
        return plan

    def get_plan(self, plan_id: str) -> Optional[SyncPlan]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT plan_json FROM sync_plans WHERE plan_id = ?", (plan_id,))
            row = cursor.fetchone()
            if row:
                return SyncPlan(**json.loads(row[0]))
        return None

    def apply(self, plan_id: str) -> Dict[str, Any]:
        plan = self.get_plan(plan_id)
        if not plan:
            raise SyncConflictError(f"Plan '{plan_id}' not found.")

        if plan.conflicts:
            raise SyncConflictError(f"Cannot apply plan with unresolved conflicts: {', '.join(plan.conflicts)}")

        results = apply_sync_plan(plan, self.agents, self.skills, self.config)
        plan.approved = True
        plan.applied = True

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sync_plans SET approved = 1, applied = 1, plan_json = ? WHERE plan_id = ?",
                (json.dumps(plan.model_dump(mode="json")), plan_id),
            )
            conn.commit()

        self.db.record_audit(
            event_type="apply_sync_plan",
            resource_type="sync_plan",
            resource_id=plan_id,
            details=results,
        )
        return results
