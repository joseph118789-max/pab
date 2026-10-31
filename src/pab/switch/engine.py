"""Universal One-Command Agent Switching & Session Handoff Engine."""

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pab.core.config import ConfigManager
from pab.core.db import Database
from pab.core.exceptions import AgentNotFoundError, PABError, ProviderExecutionError
from pab.core.models.session import NormalizedSession, SessionContext
from pab.core.security import redact_secrets
from pab.instructions.manager import InstructionManager
from pab.memory.hub import MemoryHub
from pab.providers.base import AgentProvider
from pab.providers.detector import ProviderRegistry
from pab.registry.agent_registry import AgentRegistry
from pab.skills.manager import SkillManager
from pab.switch.launcher import build_launch_command, execute_native_launch, resolve_provider_bin
from pab.switch.models import HandoffManifest, SwitchMode, SwitchPlan, SwitchResult


def get_git_info(cwd: Path) -> Dict[str, Any]:
    """Inspect Git branch, modified files, and status."""
    info = {"branch": None, "status": [], "modified_files": [], "diff_summary": ""}
    try:
        b_proc = subprocess.run(["git", "branch", "--show-current"], cwd=str(cwd), capture_output=True, text=True)
        if b_proc.returncode == 0:
            info["branch"] = b_proc.stdout.strip()

        s_proc = subprocess.run(["git", "status", "--porcelain"], cwd=str(cwd), capture_output=True, text=True)
        if s_proc.returncode == 0:
            lines = [l.strip() for l in s_proc.stdout.splitlines() if l.strip()]
            info["status"] = lines
            info["modified_files"] = [l[3:].strip() for l in lines]

        d_proc = subprocess.run(["git", "diff", "--stat"], cwd=str(cwd), capture_output=True, text=True)
        if d_proc.returncode == 0:
            info["diff_summary"] = d_proc.stdout.strip()
    except Exception:
        pass
    return info


def compute_file_hashes(directory: Path) -> Dict[str, str]:
    """Compute SHA-256 for all files in directory."""
    hashes = {}
    if not directory.is_dir():
        return hashes
    for f in directory.rglob("*"):
        if f.is_file():
            rel = str(f.relative_to(directory))
            try:
                content = f.read_bytes()
                hashes[rel] = hashlib.sha256(content).hexdigest()
            except Exception:
                pass
    return hashes


class SwitchEngine:
    """Orchestrates bidirectional agent switching, session extraction, and native launch."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config = config_manager or ConfigManager()
        self.db = Database(self.config.db_path)
        self.providers = ProviderRegistry(workspace_root=self.config.root.parent)
        self.agent_registry = AgentRegistry(self.config)
        self.skill_manager = SkillManager(self.config)
        self.instruction_manager = InstructionManager(self.config)
        self.memory_hub = MemoryHub(self.config)

    def plan_switch(
        self,
        target_provider_name: str,
        source_provider_name: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        project_path: Optional[Path] = None,
        mode: SwitchMode = SwitchMode.HANDOFF,
        no_skills: bool = False,
        no_memory: bool = False,
        extra_args: Optional[List[str]] = None,
    ) -> SwitchPlan:
        """Step 1 & 2: Detect providers, discover agent and session, and build migration plan."""
        project_dir = Path(project_path).resolve() if project_path else Path.cwd().resolve()
        warnings: List[str] = []

        # Step 1: Detect target provider
        target_provider = self.providers.get(target_provider_name.lower())
        if not target_provider:
            raise PABError(f"Destination provider '{target_provider_name}' is not supported.")

        if not target_provider.detect():
            warnings.append(f"Destination provider '{target_provider.display_name}' executable not detected on PATH.")

        # If direct launch without source migration
        if not source_provider_name:
            target_bin = resolve_provider_bin(target_provider_name) or target_provider_name
            launch_cmd = [target_bin] + (extra_args or [])
            return SwitchPlan(
                source_provider="none",
                destination_provider=target_provider_name,
                project_path=str(project_dir),
                mode=mode,
                target_launch_cmd=launch_cmd,
                warnings=warnings,
            )

        # Detect source provider
        source_provider = self.providers.get(source_provider_name.lower())
        if not source_provider:
            raise PABError(f"Source provider '{source_provider_name}' is not supported.")

        if not source_provider.detect():
            warnings.append(f"Source provider '{source_provider.display_name}' appears to be offline.")

        # Step 2: Discover source agent
        resolved_agent_id = agent_id
        if not resolved_agent_id:
            src_agents = source_provider.list_agents()
            if src_agents:
                # Pick matching or first agent
                resolved_agent_id = src_agents[0].get("id")

        # Discover source session (Intelligent Discovery)
        resolved_session_id = None
        session_reason = "No session requested"
        if mode != SwitchMode.SKILLS_ONLY:
            resolved_session_id, session_reason = self._discover_session(
                source_provider, project_dir, session_id
            )
            if not resolved_session_id:
                warnings.append(f"No active session matched project '{project_dir.name}'. Proceeding with clean handoff.")

        # Step 4: Plan skills to sync
        skills_to_sync: List[str] = []
        conflicting_skills: List[Dict[str, Any]] = []

        if not no_skills:
            skills_to_sync, conflicting_skills = self._plan_skills(
                source_provider, target_provider, resolved_agent_id, warnings
            )

        # Step 5: Plan instructions and memory
        instructions_to_transfer: List[str] = []
        memories_to_transfer: List[str] = []

        if not no_memory and mode != SwitchMode.SKILLS_ONLY:
            # Query relevant memories
            memories = self.memory_hub.search(project_dir.name)[:5]
            memories_to_transfer = [m.title for m in memories]

        # Launch command
        launch_cmd = build_launch_command(
            provider_name=target_provider_name,
            handoff_instruction=None,  # Populated during execution
            extra_args=extra_args,
        )

        return SwitchPlan(
            source_provider=source_provider_name,
            destination_provider=target_provider_name,
            project_path=str(project_dir),
            session_id=resolved_session_id,
            agent_id=resolved_agent_id,
            mode=mode,
            skills_to_sync=skills_to_sync,
            conflicting_skills=conflicting_skills,
            instructions_to_transfer=instructions_to_transfer,
            memories_to_transfer=memories_to_transfer,
            target_launch_cmd=launch_cmd,
            warnings=warnings,
        )

    def execute_switch(
        self,
        plan: SwitchPlan,
        dry_run: bool = False,
        extra_args: Optional[List[str]] = None,
    ) -> SwitchResult:
        """Execute Steps 3 to 7: Extract session, sync skills, build bundle, and launch."""
        project_dir = Path(plan.project_path)
        warnings = list(plan.warnings)

        # If direct launch without migration
        if plan.source_provider == "none":
            launch_cmd = list(plan.target_launch_cmd)
            if extra_args:
                launch_cmd.extend(extra_args)
            launched = False
            if not dry_run:
                try:
                    execute_native_launch(launch_cmd, cwd=project_dir)
                    launched = True
                except Exception as e:
                    warnings.append(f"Direct launch error: {e}")

            dummy_manifest = HandoffManifest(
                handoff_id="direct-launch",
                source_provider="none",
                destination_provider=plan.destination_provider,
                project_path=str(project_dir),
            )
            return SwitchResult(
                success=True,
                handoff_id="direct-launch",
                manifest=dummy_manifest,
                launched=launched,
                launch_cmd=launch_cmd,
                warnings=warnings,
                handoff_dir="",
            )

        source_provider = self.providers.get(plan.source_provider)
        target_provider = self.providers.get(plan.destination_provider)

        # Generate unique handoff ID
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        handoff_id = f"switch-{plan.source_provider}-to-{plan.destination_provider}-{timestamp_str}"
        handoff_dir = project_dir / ".pab" / "handoffs" / handoff_id
        if not dry_run:
            handoff_dir.mkdir(parents=True, exist_ok=True)
            (handoff_dir / "context").mkdir(parents=True, exist_ok=True)
            (handoff_dir / "skills").mkdir(parents=True, exist_ok=True)
            (handoff_dir / "instructions").mkdir(parents=True, exist_ok=True)

        # Step 3: Extract & normalize source session
        normalized_session: Optional[NormalizedSession] = None
        if plan.session_id and source_provider:
            try:
                normalized_session = source_provider.export_session(plan.session_id)
            except Exception as e:
                warnings.append(f"Failed exporting session '{plan.session_id}': {e}")

        # Git status
        git_info = get_git_info(project_dir)

        # Context components
        task_summary = ""
        objective = ""
        completed_work: List[str] = []
        pending_work: List[str] = []
        decisions: List[str] = []
        issues: List[str] = []
        modified_files = git_info.get("modified_files", [])

        if normalized_session:
            ctx = normalized_session.context
            task_summary = ctx.task_summary
            objective = ctx.original_objective
            completed_work = ctx.completed_work
            pending_work = ctx.pending_work
            decisions = ctx.technical_decisions
            issues = ctx.unresolved_issues

        if not task_summary:
            task_summary = f"Continuing development in {project_dir.name}"
        if not objective:
            objective = f"Project work in {project_dir.name}"

        # Write context markdown snippets
        if not dry_run:
            (handoff_dir / "context" / "task-summary.md").write_text(f"# Task Summary\n\n{task_summary}\n", encoding="utf-8")
            (handoff_dir / "context" / "decisions.md").write_text("# Decisions\n\n" + ("\n".join(f"- {d}" for d in decisions) if decisions else "- None recorded\n"), encoding="utf-8")
            (handoff_dir / "context" / "pending-work.md").write_text("# Pending Work\n\n" + ("\n".join(f"- [ ] {w}" for w in pending_work) if pending_work else "- None recorded\n"), encoding="utf-8")
            (handoff_dir / "context" / "project-context.md").write_text(
                f"# Project Context\n\nPath: `{project_dir}`\nGit Branch: `{git_info.get('branch') or 'N/A'}`\nModified Files: {len(modified_files)}\n",
                encoding="utf-8",
            )

        # Step 4: Synchronise skills
        synced_skills = []
        if plan.skills_to_sync and not dry_run:
            for sname in plan.skills_to_sync:
                skill = self.skill_manager.get_skill(sname)
                if skill:
                    try:
                        # Install in target provider
                        target_provider.install_skill(skill)
                        synced_skills.append(sname)
                        # Copy skill package into bundle skills/ directory
                        if skill.source_path:
                            dest = handoff_dir / "skills" / sname
                            shutil.copytree(Path(skill.source_path), dest, dirs_exist_ok=True)
                    except Exception as e:
                        warnings.append(f"Failed syncing skill '{sname}': {e}")

        # Step 5: Transfer instructions & memories
        instruction_versions = {}
        if not dry_run:
            # Transfer AGENTS.md
            agents_md = project_dir / "AGENTS.md"
            if not agents_md.is_file():
                agents_md = self.config.root / "instructions" / "AGENTS.md"
            if agents_md.is_file():
                inst_content = agents_md.read_text(encoding="utf-8")
                (handoff_dir / "instructions" / "AGENTS.md").write_text(inst_content, encoding="utf-8")
                instruction_versions["AGENTS.md"] = hashlib.sha256(inst_content.encode()).hexdigest()[:8]

                # Convert to destination native instruction file if missing
                if plan.destination_provider == "claude" and not (project_dir / "CLAUDE.md").exists():
                    (project_dir / "CLAUDE.md").write_text(inst_content, encoding="utf-8")
                elif plan.destination_provider == "agy" and not (project_dir / "GEMINI.md").exists():
                    (project_dir / "GEMINI.md").write_text(inst_content, encoding="utf-8")
                elif plan.destination_provider == "dsh" and not (project_dir / "DEEPSEEK.md").exists():
                    (project_dir / "DEEPSEEK.md").write_text(inst_content, encoding="utf-8")
                elif plan.destination_provider == "pi" and not (project_dir / "AGENTS.md").exists():
                    (project_dir / "AGENTS.md").write_text(inst_content, encoding="utf-8")

        # Step 6: Generate HANDOFF.md and manifest
        handoff_md_content = self._render_handoff_markdown(
            handoff_id=handoff_id,
            source_provider=plan.source_provider,
            target_provider=plan.destination_provider,
            session_id=plan.session_id,
            objective=objective,
            task_summary=task_summary,
            completed_work=completed_work,
            pending_work=pending_work,
            decisions=decisions,
            git_info=git_info,
            skills=synced_skills,
        )

        if not dry_run:
            (handoff_dir / "HANDOFF.md").write_text(handoff_md_content, encoding="utf-8")
            if normalized_session:
                (handoff_dir / "session.json").write_text(
                    json.dumps(normalized_session.model_dump(mode="json"), indent=2), encoding="utf-8"
                )

        # Hashes and manifest
        file_hashes = compute_file_hashes(handoff_dir) if not dry_run else {}
        manifest = HandoffManifest(
            handoff_id=handoff_id,
            source_provider=plan.source_provider,
            destination_provider=plan.destination_provider,
            source_agent_id=plan.agent_id,
            source_session_id=plan.session_id,
            project_path=str(project_dir),
            imported_skills=synced_skills,
            instruction_versions=instruction_versions,
            memory_references=plan.memories_to_transfer,
            file_hashes=file_hashes,
            migration_warnings=warnings,
        )

        if not dry_run:
            (handoff_dir / "manifest.json").write_text(
                json.dumps(manifest.model_dump(mode="json"), indent=2), encoding="utf-8"
            )

        # Step 7: Formulate handoff instruction and launch
        handoff_rel_path = f".pab/handoffs/{handoff_id}/HANDOFF.md"
        handoff_instruction = (
            f"You are continuing work transferred from {source_provider.display_name if source_provider else plan.source_provider}.\n\n"
            f"Read the following handoff documentation:\n"
            f"{handoff_rel_path}\n\n"
            f"Review the relevant project context, instructions and skills.\n"
            f"Continue the outstanding task from the previous agent.\n"
            f"Do not blindly repeat completed work.\n"
            f"Verify the current repository state before making modifications.\n"
            f"Preserve all existing changes."
        )

        launch_cmd = build_launch_command(
            provider_name=plan.destination_provider,
            handoff_instruction=handoff_instruction,
            handoff_md_path=str(handoff_dir / "HANDOFF.md"),
            extra_args=extra_args,
        )

        launched = False
        if not dry_run:
            # Record switch history in DB
            self.db.record_switch({
                "handoff_id": handoff_id,
                "source_provider": plan.source_provider,
                "target_provider": plan.destination_provider,
                "source_session_id": plan.session_id,
                "source_agent_id": plan.agent_id,
                "project_path": str(project_dir),
                "mode": plan.mode.value,
                "skills_synced": synced_skills,
                "warnings": warnings,
                "manifest": manifest.model_dump(mode="json"),
                "launched": False,
            })

            try:
                execute_native_launch(launch_cmd, cwd=project_dir)
                launched = True
                # Update launched flag
                self.db.record_switch({
                    "handoff_id": handoff_id,
                    "source_provider": plan.source_provider,
                    "target_provider": plan.destination_provider,
                    "source_session_id": plan.session_id,
                    "source_agent_id": plan.agent_id,
                    "project_path": str(project_dir),
                    "mode": plan.mode.value,
                    "skills_synced": synced_skills,
                    "warnings": warnings,
                    "manifest": manifest.model_dump(mode="json"),
                    "launched": True,
                })
            except Exception as e:
                warnings.append(f"CLI launch notice: {e}")

        return SwitchResult(
            success=True,
            handoff_id=handoff_id,
            manifest=manifest,
            launched=launched,
            launch_cmd=launch_cmd,
            warnings=warnings,
            handoff_dir=str(handoff_dir),
        )

    def rollback_switch(self, handoff_id: str) -> bool:
        """Roll back destination configuration from a switch operation."""
        record = self.db.get_switch_by_handoff(handoff_id)
        if not record:
            raise PABError(f"Switch record '{handoff_id}' not found in history.")

        project_dir = Path(record["project_path"])
        handoff_dir = project_dir / ".pab" / "handoffs" / handoff_id
        if handoff_dir.is_dir():
            shutil.rmtree(handoff_dir, ignore_errors=True)
            return True
        return False

    def _discover_session(
        self,
        provider: AgentProvider,
        project_dir: Path,
        requested_session: Optional[str],
    ) -> Tuple[Optional[str], str]:
        """Intelligently match session by project and recency."""
        if requested_session and requested_session.lower() != "latest":
            return requested_session, f"Specified session ID {requested_session}"

        sessions = provider.list_sessions()
        if not sessions:
            return None, "No sessions found on provider"

        if requested_session and requested_session.lower() == "latest":
            return sessions[0]["id"], "Requested latest session"

        project_name = project_dir.name.lower()
        project_path_str = str(project_dir.resolve()).lower()

        scored = []
        for s in sessions:
            score = 0
            s_id = str(s.get("id", ""))
            s_proj = str(s.get("project", "")).lower()
            s_path = str(s.get("session_path") or s.get("transcript_path") or s.get("session_file") or "").lower()

            if s_proj and s_proj == project_name:
                score += 100
            elif s_proj and s_proj in project_path_str:
                score += 50

            if project_path_str in s_path:
                score += 80
            elif project_name in s_path:
                score += 40

            mtime = s.get("modified_at") or 0
            scored.append((score, mtime, s_id))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        if scored and scored[0][0] > 0:
            return scored[0][2], f"Matched project '{project_name}'"

        return None, f"No session matched project '{project_name}'"

    def _plan_skills(
        self,
        source_provider: AgentProvider,
        target_provider: AgentProvider,
        agent_id: Optional[str],
        warnings: List[str],
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        skills_to_sync: List[str] = []
        conflicts: List[Dict[str, Any]] = []

        # Find skills associated with agent
        agent_skills = []
        if agent_id:
            ag = source_provider.get_agent(agent_id)
            if ag:
                agent_skills = ag.get("skills", [])
            else:
                canonical = self.agent_registry.get_agent(agent_id)
                if canonical:
                    agent_skills = canonical.agent.capabilities.skills

        dest_skills = {s["name"]: s for s in target_provider.list_skills()}

        for sname in agent_skills:
            canonical_skill = self.skill_manager.get_skill(sname)
            if not canonical_skill:
                continue

            if sname in dest_skills:
                # Check version conflict
                dest_version = dest_skills[sname].get("version", "1.0.0")
                src_version = canonical_skill.manifest.metadata.version or "1.0.0"
                if dest_version != src_version:
                    conflicts.append({
                        "name": sname,
                        "source_version": src_version,
                        "destination_version": dest_version,
                    })
                    warnings.append(
                        f"Skill version conflict for '{sname}': Destination={dest_version}, Source={src_version}"
                    )
            else:
                skills_to_sync.append(sname)

        return skills_to_sync, conflicts

    def _render_handoff_markdown(
        self,
        handoff_id: str,
        source_provider: str,
        target_provider: str,
        session_id: Optional[str],
        objective: str,
        task_summary: str,
        completed_work: List[str],
        pending_work: List[str],
        decisions: List[str],
        git_info: Dict[str, Any],
        skills: List[str],
    ) -> str:
        completed_md = "\n".join(f"- [x] {w}" for w in completed_work) if completed_work else "- None recorded"
        pending_md = "\n".join(f"- [ ] {w}" for w in pending_work) if pending_work else "- Continue task as directed"
        decisions_md = "\n".join(f"- {d}" for d in decisions) if decisions else "- None recorded"
        skills_md = ", ".join(skills) if skills else "None"
        modified_files = git_info.get("modified_files", [])
        files_md = "\n".join(f"- `{f}`" for f in modified_files) if modified_files else "- Clean working tree"

        md = (
            f"# PersonaOS Agent Handoff Bundle\n\n"
            f"- **Handoff ID:** `{handoff_id}`\n"
            f"- **Source Agent / Provider:** {source_provider.capitalize()}\n"
            f"- **Destination Provider:** {target_provider.capitalize()}\n"
            f"- **Source Session ID:** `{session_id or 'clean-launch'}`\n"
            f"- **Export Timestamp:** {datetime.now(timezone.utc).isoformat()}\n"
            f"- **Git Branch:** `{git_info.get('branch') or 'N/A'}`\n"
            f"- **Transferred Skills:** {skills_md}\n\n"
            f"---\n\n"
            f"## 1. Original User Objective\n"
            f"> {objective}\n\n"
            f"## 2. Current Task Summary\n"
            f"{task_summary}\n\n"
            f"## 3. Completed Work\n"
            f"{completed_md}\n\n"
            f"## 4. Pending Work & Next Recommended Actions\n"
            f"{pending_md}\n\n"
            f"## 5. Architectural & Technical Decisions\n"
            f"{decisions_md}\n\n"
            f"## 6. Git Working Tree & Modified Files\n"
            f"{files_md}\n\n"
            f"---\n\n"
            f"### Agent Instructions\n"
            f"1. You are continuing work previously performed under {source_provider}.\n"
            f"2. Inspect the repository state before executing destructive actions.\n"
            f"3. Do not blindly repeat tasks marked completed above.\n"
            f"4. Preserve all working directory changes.\n"
        )
        return redact_secrets(md)
