"""AGY worker registry and profile resolution.

Maps a logical worker identity (e.g. `sales`) to the on-disk artefacts required to
execute it with an isolated AGY profile:

* ``workdir``      — the working directory the AGY process runs in.
* ``profile``      — the AGY profile name (e.g. ``seekn``).
* ``profile_home`` — the isolated HOME for that profile (``~/.agy-<profile>``).

Resolution is deliberately tolerant about *where* the worker directory lives: the same
Sentinel Ops agent tree exists under more than one root (``/root/projects/...`` and
``/root/.openclaw/workspace/projects/...``). Path matching therefore works on the
resolved absolute path and on the trailing ``agents/<worker>`` components, so an
absolute ``--worktree`` always resolves to the correct AGY profile instead of silently
falling back to the default profile.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from pab.core.exceptions import PABError


class AgyWorkerResolutionError(PABError):
    """Raised when a worker id / worktree cannot be mapped onto an AGY profile."""


# Default Sentinel Ops AGY workers. Overridable via PAB config `custom.agy_workers`
# or the `PAB_AGY_WORKERS` environment variable (JSON list of worker definitions).
DEFAULT_AGY_WORKERS: List[Dict[str, Any]] = [
    {
        "id": "automation",
        "label": "AGY-Automation",
        "profile": "cylyl",
        "responsibility": "Automate repetitive Sentinel workflows and internal tooling",
    },
    {
        "id": "delivery",
        "label": "AGY-Delivery",
        "profile": "93975",
        "responsibility": "Customer onboarding, Wazuh deployment, monitoring, reports",
    },
    {
        "id": "qa",
        "label": "AGY-QA",
        "profile": "ogui",
        "responsibility": "Test delivery, validate reports, security/configuration QA",
    },
    {
        "id": "research",
        "label": "AGY-Research",
        "profile": "yk2012",
        "responsibility": "Market research, prospect research, competitor/industry intelligence",
    },
    {
        "id": "sales",
        "label": "AGY-Sales",
        "profile": "seekn",
        "responsibility": "Leads, prospects, outreach, follow-up, proposals",
    },
]

DEFAULT_WORKER_BASE = Path("/root/projects/sentinel_ops/agents")
# Isolated AGY profile homes live next to the real HOME as ``~/.agy-<profile>``.
DEFAULT_PROFILE_ROOT = Path.home()


@dataclass(frozen=True)
class AgyWorkerProfile:
    """Resolved execution target for a single AGY worker."""

    worker_id: str
    label: str
    profile: str
    workdir: Path
    profile_home: Path
    responsibility: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "label": self.label,
            "profile": self.profile,
            "workdir": str(self.workdir),
            "profile_home": str(self.profile_home),
            "responsibility": self.responsibility,
        }


class AgyWorkerRegistry:
    """Resolves worker identities and worktree paths to AGY profiles."""

    def __init__(
        self,
        workers: Optional[List[Dict[str, Any]]] = None,
        worker_base: Optional[Path] = None,
        profile_root: Optional[Path] = None,
    ):
        self._worker_base = Path(worker_base or os.environ.get("PAB_AGY_WORKER_BASE") or DEFAULT_WORKER_BASE)
        self._profile_root = Path(
            profile_root or os.environ.get("PAB_AGY_PROFILE_ROOT") or DEFAULT_PROFILE_ROOT
        )
        self._workers: Dict[str, AgyWorkerProfile] = {}

        for definition in workers if workers is not None else DEFAULT_AGY_WORKERS:
            self._register(definition)

    # -- construction ------------------------------------------------------
    def _register(self, definition: Dict[str, Any]) -> None:
        worker_id = str(definition["id"]).strip()
        if not worker_id:
            raise AgyWorkerResolutionError("AGY worker definition is missing an 'id'.")

        profile = str(definition.get("profile") or worker_id)
        workdir = Path(definition.get("workdir") or (self._worker_base / worker_id)).expanduser()
        profile_home = Path(
            definition.get("profile_home") or (self._profile_root / f".agy-{profile}")
        ).expanduser()

        self._workers[worker_id.lower()] = AgyWorkerProfile(
            worker_id=worker_id,
            label=str(definition.get("label") or f"AGY-{worker_id.title()}"),
            profile=profile,
            workdir=workdir,
            profile_home=profile_home,
            responsibility=str(definition.get("responsibility") or ""),
        )

    @classmethod
    def from_config(cls, config_manager: Optional[Any] = None) -> "AgyWorkerRegistry":
        """Build a registry from PAB configuration, falling back to defaults."""
        definitions: Optional[List[Dict[str, Any]]] = None
        worker_base: Optional[Path] = None
        profile_root: Optional[Path] = None

        env_defs = os.environ.get("PAB_AGY_WORKERS")
        if env_defs:
            import json

            try:
                parsed = json.loads(env_defs)
                if isinstance(parsed, list):
                    definitions = parsed
            except Exception:
                pass

        if config_manager is not None:
            custom = getattr(getattr(config_manager, "settings", None), "custom", None) or {}
        else:
            custom = {}
            cfg_path = Path(os.environ.get("PAB_HOME") or (Path.home() / ".pab")) / "config.yaml"
            if cfg_path.is_file():
                try:
                    import yaml

                    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
                    custom = data.get("custom") or {}
                except Exception:
                    custom = {}

        if definitions is None and isinstance(custom.get("agy_workers"), list):
            definitions = custom["agy_workers"]
        if custom.get("agy_worker_base"):
            worker_base = Path(custom["agy_worker_base"])
        if custom.get("agy_profile_root"):
            profile_root = Path(custom["agy_profile_root"])

        return cls(workers=definitions, worker_base=worker_base, profile_root=profile_root)

    # -- queries -----------------------------------------------------------
    def list_workers(self) -> List[AgyWorkerProfile]:
        return sorted(self._workers.values(), key=lambda w: w.worker_id)

    def get(self, worker_id: str) -> Optional[AgyWorkerProfile]:
        if not worker_id:
            return None
        return self._workers.get(worker_id.strip().lower())

    # -- resolution --------------------------------------------------------
    def resolve(
        self,
        worker_id: Optional[str] = None,
        worktree: Optional[Path] = None,
    ) -> AgyWorkerProfile:
        """
        Resolve an AGY worker profile.

        Resolution order:
        1. Exact worker id match (case-insensitive). An explicitly requested but
           unknown worker id is an error — it is never silently remapped.
        2. No worker id → match the worktree against the known worker dirs, by
           resolved absolute path, by trailing ``agents/<id>`` components, or by
           directory name.
        """
        if worker_id:
            match = self.get(worker_id)
            if match:
                return match
            raise AgyWorkerResolutionError(
                f"Unknown AGY worker '{worker_id}'. "
                f"Known workers: {', '.join(sorted(self._workers.keys()))}."
            )

        if worktree is not None:
            path_match = self._match_by_path(Path(worktree))
            if path_match:
                return path_match

        known = ", ".join(sorted(self._workers.keys()))
        if worker_id:
            raise AgyWorkerResolutionError(
                f"Unknown AGY worker '{worker_id}'. "
                f"Known workers: {known}. "
                f"Provide an absolute --worktree inside a worker directory to resolve by path."
            )
        raise AgyWorkerResolutionError(
            f"Could not resolve an AGY worker for worktree '{worktree}'. Known workers: {known}."
        )

    def _match_by_path(self, path: Path) -> Optional[AgyWorkerProfile]:
        try:
            resolved = path.expanduser().resolve()
        except Exception:
            resolved = path

        for worker in self._workers.values():
            try:
                if worker.workdir.expanduser().resolve() == resolved:
                    return worker
            except Exception:
                if worker.workdir == resolved:
                    return worker

        # Trailing components match, e.g. ".../agents/sales" -> sales
        parts = resolved.parts
        for worker in self._workers.values():
            if len(parts) >= 2 and parts[-2] == "agents" and parts[-1] == worker.worker_id:
                return worker

        # Directory name equals the worker id
        if parts:
            by_name = self.get(parts[-1])
            if by_name:
                return by_name

        return None
