"""Cross-Platform Session Migration and Handoff Manager."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pab.core.config import ConfigManager
from pab.core.db import Database
from pab.core.exceptions import PABError, ProviderExecutionError
from pab.core.models.session import HandoffBundle, NormalizedSession
from pab.providers.detector import ProviderRegistry
from pab.sessions.handoff import create_handoff_package


class SessionMigrationManager:
    """Manages session inventory, normalization, portable handoff, and resume."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config = config_manager or ConfigManager()
        self.db = Database(self.config.db_path)
        self.providers = ProviderRegistry(workspace_root=self.config.root.parent)

    def list_sessions(self, provider_name: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        targets = [provider_name] if provider_name else list(self.providers._providers.keys())

        for p_name in targets:
            provider = self.providers.get(p_name)
            if provider:
                sess_list = provider.list_sessions()
                for s in sess_list:
                    s["provider"] = p_name
                    results.append(s)
        return results

    def export_session(self, provider_name: str, session_id: str) -> NormalizedSession:
        provider = self.providers.get(provider_name)
        if not provider:
            raise PABError(f"Provider '{provider_name}' not found.")

        normalized = provider.export_session(session_id)
        if not normalized:
            raise PABError(f"Failed to export session '{session_id}' from {provider_name}")

        # Store in DB & sessions directory
        export_file = self.config.sessions_dir / "exports" / f"{normalized.id}.json"
        export_file.parent.mkdir(parents=True, exist_ok=True)
        export_file.write_text(json.dumps(normalized.model_dump(mode="json"), indent=2), encoding="utf-8")

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO sessions (
                    id, source_provider, source_session_id, project, created_at, exported_at, data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized.id,
                    normalized.source_provider,
                    normalized.source_session_id,
                    normalized.project,
                    normalized.created_at,
                    normalized.exported_at,
                    json.dumps(normalized.model_dump(mode="json")),
                ),
            )
            conn.commit()

        self.db.record_audit(
            event_type="export_session",
            resource_type="session",
            resource_id=session_id,
            provider=provider_name,
        )
        return normalized

    def create_handoff(
        self,
        from_provider: str,
        to_provider: Optional[str],
        session_id: str,
    ) -> HandoffBundle:
        norm = self.export_session(from_provider, session_id)
        handoffs_dir = self.config.sessions_dir / "handoffs"
        bundle = create_handoff_package(norm, to_provider, handoffs_dir)
        self.db.record_audit(
            event_type="create_handoff",
            resource_type="session",
            resource_id=session_id,
            provider=from_provider,
            details={"target_provider": to_provider, "bundle_id": bundle.bundle_id},
        )
        return bundle

    def import_context(
        self,
        target_provider: str,
        session_id: str,
        target_workspace: Optional[Path] = None,
    ) -> Path:
        """Inject handoff package context into the target provider's workspace."""
        provider = self.providers.get(target_provider)
        if not provider:
            raise PABError(f"Target provider '{target_provider}' not found.")

        norm = self.get_normalized_session(session_id)
        if not norm:
            raise PABError(f"Session '{session_id}' has not been exported yet. Run export first.")

        # Determine workspace destination
        if target_workspace:
            dest_dir = target_workspace
        else:
            dest_dir = self.config.root.parent

        dest_dir.mkdir(parents=True, exist_ok=True)
        handoff_file = dest_dir / "HANDOFF.md"

        # Generate handoff markdown
        from pab.sessions.handoff import generate_handoff_markdown
        handoff_content = generate_handoff_markdown(norm, target_provider)
        handoff_file.write_text(handoff_content, encoding="utf-8")

        self.db.record_audit(
            event_type="import_context",
            resource_type="session",
            resource_id=session_id,
            provider=target_provider,
            details={"dest_path": str(handoff_file)},
        )
        return handoff_file

    def get_normalized_session(self, session_id: str) -> Optional[NormalizedSession]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data_json FROM sessions WHERE id = ? OR source_session_id = ?",
                (session_id, session_id),
            )
            row = cursor.fetchone()
            if row:
                return NormalizedSession(**json.loads(row[0]))
        return None

    def resume_session(self, provider_name: str, session_id: str) -> bool:
        """
        Trigger native resume for the given provider.
        Cross-provider native resume is explicitly blocked as unsupported by design.
        """
        provider = self.providers.get(provider_name)
        if not provider:
            raise PABError(f"Provider '{provider_name}' not found.")

        norm = self.get_normalized_session(session_id)
        if norm and norm.source_provider != provider_name:
            raise ProviderExecutionError(
                f"Direct native resume across different providers is unsupported: session originated on '{norm.source_provider}', "
                f"requested on '{provider_name}'. Use 'pab session handoff --from {norm.source_provider} --to {provider_name} --session {session_id}' instead."
            )

        return provider.resume_session(session_id)
