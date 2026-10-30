"""PersonaOS Agent Bridge (PAB) orchestration bridge."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.config import ConfigManager
from pab.core.models.agent import CanonicalAgentProfile
from pab.personaos.profile_converter import load_personaos_profile
from pab.registry.agent_registry import AgentRegistry
from pab.skills.manager import SkillManager


class PersonaOSBridge:
    """Non-intrusive management bridge for PersonaOS worker profiles."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config = config_manager or ConfigManager()
        self.registry = AgentRegistry(self.config)
        self.skills = SkillManager(self.config)

    def import_worker_profile(self, profile_file: Path) -> CanonicalAgentProfile:
        definition = load_personaos_profile(profile_file)
        existing = self.registry.get_agent(definition.id)
        if existing:
            return self.registry.update_agent(definition, commit_message="Imported from PersonaOS")
        return self.registry.create_agent(definition)

    def sync_worker_profiles(
        self,
        profiles_dir: Path,
        target_providers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Scan PersonaOS profiles directory, register agents, and deploy to providers."""
        results = {"imported": [], "deployed": {}}
        if not profiles_dir.is_dir():
            return results

        targets = target_providers or ["openclaw"]

        for worker_dir in profiles_dir.iterdir():
            if worker_dir.is_dir():
                v1_yaml = worker_dir / "v1.yaml"
                if v1_yaml.is_file():
                    profile = self.import_worker_profile(v1_yaml)
                    results["imported"].append(profile.agent.id)

                    # Deploy agent to target providers
                    deploy_res = self.registry.deploy_agent(profile.agent.id, targets)
                    results["deployed"][profile.agent.id] = deploy_res

                    # Auto-provision canonical skills
                    for skill_name in profile.agent.capabilities.skills:
                        if not self.skills.get_skill(skill_name):
                            self.skills.create_skill(
                                name=skill_name,
                                description=f"Skill for PersonaOS worker {profile.agent.name}",
                            )
                        self.skills.deploy_skill(skill_name, targets)

        return results

    def get_readiness_report(self) -> Dict[str, Any]:
        """Report provider health and deployed agent counts for PersonaOS scheduler."""
        provider_status = self.registry.providers.detect_all()
        agents = self.registry.list_agents()
        return {
            "providers": provider_status,
            "registered_agents": len(agents),
            "agents": [a.agent.id for a in agents],
        }
