"""Universal Skill Management service."""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from pab.core.config import ConfigManager
from pab.core.db import Database
from pab.core.exceptions import SkillValidationError
from pab.core.models.skill import (
    CanonicalSkill,
    SkillManifest,
    SkillMetadata,
    SkillResource,
)
from pab.providers.detector import ProviderRegistry
from pab.skills.scanner import scan_skill_security
from pab.skills.validator import validate_skill_structure


class SkillManager:
    """Manages the canonical Open Agent Skills library and deployment."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config = config_manager or ConfigManager()
        self.db = Database(self.config.db_path)
        self.providers = ProviderRegistry(workspace_root=self.config.root.parent)

    def list_skills(self) -> List[CanonicalSkill]:
        skills = []
        if not self.config.skills_dir.is_dir():
            return skills

        for skill_dir in self.config.skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").is_file():
                skill = self._load_skill_from_dir(skill_dir)
                if skill:
                    skills.append(skill)
        return skills

    def get_skill(self, name: str) -> Optional[CanonicalSkill]:
        skill_dir = self.config.skills_dir / name
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
            return None
        return self._load_skill_from_dir(skill_dir)

    def _load_skill_from_dir(self, skill_dir: Path) -> Optional[CanonicalSkill]:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            return None
        text = skill_md.read_text(encoding="utf-8")
        manifest_data = {}
        body = text

        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                manifest_data = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()

        manifest = SkillManifest(
            name=manifest_data.get("name", skill_dir.name),
            description=manifest_data.get("description", ""),
            metadata=SkillMetadata(**manifest_data.get("metadata", {})),
            dependencies=manifest_data.get("dependencies", []),
            license=manifest_data.get("license"),
        )

        scripts = self._collect_resources(skill_dir / "scripts", is_exec=True)
        references = self._collect_resources(skill_dir / "references")
        assets = self._collect_resources(skill_dir / "assets")

        return CanonicalSkill(
            manifest=manifest,
            body=body,
            scripts=scripts,
            references=references,
            assets=assets,
            source_path=str(skill_dir),
        )

    def _collect_resources(self, directory: Path, is_exec: bool = False) -> List[SkillResource]:
        resources = []
        if not directory.is_dir():
            return resources
        for f in directory.rglob("*"):
            if f.is_file():
                rel_path = str(f.relative_to(directory.parent))
                try:
                    content = f.read_bytes()
                    chash = hashlib.sha256(content).hexdigest()
                    size = len(content)
                    resources.append(
                        SkillResource(
                            relative_path=rel_path,
                            content_hash=chash,
                            size_bytes=size,
                            is_executable=is_exec,
                        )
                    )
                except Exception:
                    pass
        return resources

    def create_skill(self, name: str, description: str, body: Optional[str] = None) -> CanonicalSkill:
        target_dir = self.config.skills_dir / name
        if target_dir.exists():
            raise SkillValidationError(f"Skill '{name}' already exists in library.")

        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "scripts").mkdir(exist_ok=True)
        (target_dir / "references").mkdir(exist_ok=True)
        (target_dir / "assets").mkdir(exist_ok=True)

        skill_body = body or f"# {name.capitalize()} Skill\n\n## Overview\n{description}\n\n## Workflow\n1. Inspect context\n2. Perform operation\n"
        manifest = SkillManifest(name=name, description=description)

        skill = CanonicalSkill(
            manifest=manifest,
            body=skill_body,
            source_path=str(target_dir),
        )

        # Write SKILL.md
        skill_md = target_dir / "SKILL.md"
        frontmatter = yaml.safe_dump(manifest.model_dump(), sort_keys=False)
        content = f"---\n{frontmatter}---\n\n{skill_body}\n"
        skill_md.write_text(content, encoding="utf-8")

        # Record in DB
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO skills (name, version, manifest_json, path, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    manifest.metadata.version or "1.0.0",
                    json.dumps(manifest.model_dump(mode="json")),
                    str(target_dir),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

        self.db.record_audit(
            event_type="create_skill",
            resource_type="skill",
            resource_id=name,
            details={"description": description},
        )
        return skill

    def import_skill(self, source_path: Path) -> CanonicalSkill:
        src = source_path.resolve()
        if not src.is_dir() or not (src / "SKILL.md").is_file():
            raise SkillValidationError(f"Invalid skill source directory: {source_path}")

        temp_skill = self._load_skill_from_dir(src)
        if not temp_skill:
            raise SkillValidationError(f"Failed to parse skill at {source_path}")

        issues = validate_skill_structure(temp_skill)
        if issues:
            raise SkillValidationError(f"Validation failed for imported skill: {', '.join(issues)}")

        name = temp_skill.manifest.name
        dest = self.config.skills_dir / name
        shutil.copytree(src, dest, dirs_exist_ok=True)

        imported = self._load_skill_from_dir(dest)
        if not imported:
            raise SkillValidationError(f"Could not load imported skill from {dest}")

        # Record in DB & audit
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO skills (name, version, manifest_json, path, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    imported.manifest.metadata.version or "1.0.0",
                    json.dumps(imported.manifest.model_dump(mode="json")),
                    str(dest),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

        self.db.record_audit(
            event_type="import_skill",
            resource_type="skill",
            resource_id=name,
            details={"source": str(src)},
        )
        return imported

    def export_skill(self, name: str, target_dir: Path) -> Path:
        skill = self.get_skill(name)
        if not skill or not skill.source_path:
            raise SkillValidationError(f"Skill '{name}' not found")

        target = target_dir.resolve() / name
        shutil.copytree(Path(skill.source_path), target, dirs_exist_ok=True)
        return target

    def validate_skill(self, name: str) -> List[str]:
        skill = self.get_skill(name)
        if not skill:
            raise SkillValidationError(f"Skill '{name}' not found")
        return validate_skill_structure(skill)

    def audit_skill(self, name: str) -> Dict[str, Any]:
        skill = self.get_skill(name)
        if not skill:
            raise SkillValidationError(f"Skill '{name}' not found")
        return scan_skill_security(skill)

    def deploy_skill(self, name: str, target_providers: List[str]) -> Dict[str, Any]:
        skill = self.get_skill(name)
        if not skill:
            raise SkillValidationError(f"Skill '{name}' not found")

        # Security check before deploy
        security_audit = scan_skill_security(skill)
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

            try:
                ok = provider.install_skill(skill)
                results[p_name] = {
                    "success": ok,
                    "security_audit": security_audit,
                }
                self.db.record_audit(
                    event_type="deploy_skill",
                    resource_type="skill",
                    resource_id=name,
                    provider=p_name,
                    details={"is_safe": security_audit["is_safe"]},
                )
            except Exception as e:
                results[p_name] = {"success": False, "error": str(e)}

        return results

    def sync_skills(self, target_providers: List[str]) -> Dict[str, Any]:
        all_skills = self.list_skills()
        sync_results = {}
        for s in all_skills:
            sync_results[s.manifest.name] = self.deploy_skill(s.manifest.name, target_providers)
        return sync_results
