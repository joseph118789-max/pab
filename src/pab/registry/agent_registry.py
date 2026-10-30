"""Canonical Agent Registry service."""

import difflib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from pab.core.config import ConfigManager
from pab.core.db import Database
from pab.core.exceptions import AgentNotFoundError, AgentValidationError
from pab.core.models.agent import CanonicalAgentDefinition, CanonicalAgentProfile
from pab.providers.detector import ProviderRegistry


class AgentRegistry:
    """Manages canonical agent definitions, versioning, diff, and deployment."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config = config_manager or ConfigManager()
        self.db = Database(self.config.db_path)
        self.providers = ProviderRegistry(workspace_root=self.config.root.parent)

    def list_agents(self) -> List[CanonicalAgentProfile]:
        profiles = []
        if not self.config.agents_dir.is_dir():
            return profiles

        for agent_dir in self.config.agents_dir.iterdir():
            if agent_dir.is_dir():
                yaml_file = agent_dir / "agent.yaml"
                if yaml_file.is_file():
                    try:
                        with open(yaml_file, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f)
                        profiles.append(CanonicalAgentProfile(**data))
                    except Exception:
                        continue
        return profiles

    def get_agent(self, agent_id: str) -> Optional[CanonicalAgentProfile]:
        yaml_file = self.config.agents_dir / agent_id / "agent.yaml"
        if not yaml_file.is_file():
            return None
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return CanonicalAgentProfile(**data)

    def create_agent(self, definition: CanonicalAgentDefinition) -> CanonicalAgentProfile:
        agent_dir = self.config.agents_dir / definition.id
        if agent_dir.exists():
            raise AgentValidationError(f"Agent with ID '{definition.id}' already exists.")

        agent_dir.mkdir(parents=True, exist_ok=True)
        history_dir = agent_dir / "history"
        history_dir.mkdir(exist_ok=True)
        instructions_dir = agent_dir / "instructions"
        instructions_dir.mkdir(exist_ok=True)

        # Default instruction files
        (instructions_dir / "AGENTS.md").write_text(
            f"# {definition.name} Instructions\n\n{definition.identity.objective}\n",
            encoding="utf-8",
        )
        (instructions_dir / "USER.md").write_text(
            "# User Preferences\n\nBe concise and technical.\n",
            encoding="utf-8",
        )

        profile = CanonicalAgentProfile(agent=definition)
        yaml_path = agent_dir / "agent.yaml"
        yaml_content = yaml.safe_dump(profile.model_dump(), sort_keys=False)
        yaml_path.write_text(yaml_content, encoding="utf-8")

        # Snapshot history
        snap_path = history_dir / f"v_{definition.version}.yaml"
        snap_path.write_text(yaml_content, encoding="utf-8")

        # Record in DB & audit
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO agents (id, name, version, schema_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    definition.id,
                    definition.name,
                    definition.version,
                    json.dumps(profile.model_dump(mode="json")),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            cursor.execute(
                """
                INSERT INTO agent_history (agent_id, version, schema_json, created_at, commit_message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    definition.id,
                    definition.version,
                    json.dumps(profile.model_dump(mode="json")),
                    datetime.now(timezone.utc).isoformat(),
                    "Initial creation",
                ),
            )
            conn.commit()

        self.db.record_audit(
            event_type="create_agent",
            resource_type="agent",
            resource_id=definition.id,
            details={"version": definition.version, "name": definition.name},
        )
        return profile

    def update_agent(
        self,
        definition: CanonicalAgentDefinition,
        commit_message: str = "Agent updated",
    ) -> CanonicalAgentProfile:
        agent_dir = self.config.agents_dir / definition.id
        if not agent_dir.is_dir():
            raise AgentNotFoundError(f"Agent '{definition.id}' does not exist.")

        history_dir = agent_dir / "history"
        history_dir.mkdir(exist_ok=True)

        profile = CanonicalAgentProfile(agent=definition)
        yaml_path = agent_dir / "agent.yaml"
        yaml_content = yaml.safe_dump(profile.model_dump(), sort_keys=False)
        yaml_path.write_text(yaml_content, encoding="utf-8")

        # Snapshot history
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        snap_path = history_dir / f"v_{definition.version}_{timestamp}.yaml"
        snap_path.write_text(yaml_content, encoding="utf-8")

        # Record in DB & audit
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO agents (id, name, version, schema_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    definition.id,
                    definition.name,
                    definition.version,
                    json.dumps(profile.model_dump(mode="json")),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            cursor.execute(
                """
                INSERT INTO agent_history (agent_id, version, schema_json, created_at, commit_message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    definition.id,
                    definition.version,
                    json.dumps(profile.model_dump(mode="json")),
                    datetime.now(timezone.utc).isoformat(),
                    commit_message,
                ),
            )
            conn.commit()

        self.db.record_audit(
            event_type="update_agent",
            resource_type="agent",
            resource_id=definition.id,
            details={"commit_message": commit_message, "version": definition.version},
        )
        return profile

    def clone_agent(self, source_id: str, new_id: str, new_name: str) -> CanonicalAgentProfile:
        source = self.get_agent(source_id)
        if not source:
            raise AgentNotFoundError(f"Source agent '{source_id}' does not exist.")

        cloned_def = source.agent.model_copy(deep=True)
        cloned_def.id = new_id
        cloned_def.name = new_name
        cloned_def.version = "1.0.0"
        return self.create_agent(cloned_def)

    def delete_agent(self, agent_id: str) -> bool:
        agent_dir = self.config.agents_dir / agent_id
        if not agent_dir.is_dir():
            return False

        shutil.rmtree(agent_dir, ignore_errors=True)
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            conn.commit()

        self.db.record_audit(
            event_type="delete_agent",
            resource_type="agent",
            resource_id=agent_id,
        )
        return True

    def diff_agent(self, agent_id: str, new_definition: CanonicalAgentDefinition) -> str:
        current = self.get_agent(agent_id)
        if not current:
            raise AgentNotFoundError(f"Agent '{agent_id}' does not exist.")

        cur_yaml = yaml.safe_dump(current.model_dump(), sort_keys=False)
        new_profile = CanonicalAgentProfile(agent=new_definition)
        new_yaml = yaml.safe_dump(new_profile.model_dump(), sort_keys=False)

        diff = difflib.unified_diff(
            cur_yaml.splitlines(keepends=True),
            new_yaml.splitlines(keepends=True),
            fromfile=f"{agent_id} (current)",
            tofile=f"{agent_id} (proposed)",
        )
        return "".join(diff)

    def rollback_agent(self, agent_id: str, target_version: str) -> CanonicalAgentProfile:
        agent_dir = self.config.agents_dir / agent_id
        history_dir = agent_dir / "history"
        if not history_dir.is_dir():
            raise AgentNotFoundError(f"No history for agent '{agent_id}'")

        match_file = None
        for hf in history_dir.iterdir():
            if target_version in hf.name:
                match_file = hf
                break

        if not match_file or not match_file.is_file():
            raise AgentNotFoundError(f"Version '{target_version}' not found for agent '{agent_id}'")

        with open(match_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        profile = CanonicalAgentProfile(**data)
        return self.update_agent(profile.agent, commit_message=f"Rollback to {target_version}")

    def deploy_agent(self, agent_id: str, target_providers: List[str]) -> Dict[str, Any]:
        profile = self.get_agent(agent_id)
        if not profile:
            raise AgentNotFoundError(f"Agent '{agent_id}' does not exist.")

        results = {}
        targets = (
            list(self.providers._providers.keys())
            if "all" in target_providers
            else target_providers
        )

        for p_name in targets:
            provider = self.providers.get(p_name)
            if not provider:
                results[p_name] = {"success": False, "error": f"Provider '{p_name}' not supported"}
                continue

            warnings = provider.validate(profile.agent)
            try:
                res = provider.create_agent(profile.agent)
                results[p_name] = {
                    "success": True,
                    "result": res,
                    "warnings": warnings,
                }
                self.db.record_audit(
                    event_type="deploy_agent",
                    resource_type="agent",
                    resource_id=agent_id,
                    provider=p_name,
                    details={"warnings": warnings},
                )
            except Exception as e:
                results[p_name] = {"success": False, "error": str(e), "warnings": warnings}

        return results
