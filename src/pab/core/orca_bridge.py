"""Orca ADE Orchestration & Worktree Integration Bridge.

Provides bidirectional interoperability between PAB Universal Control Plane and Orca ADE:
- CLI executable resolution (ORCA_CLI_COMMAND, orca-ide, orca)
- Worktree discovery and validation
- Run creation and inspection
- Event bridging: relays Pi execution events (agent_settled, heartbeats) as Orca orchestration messages
- Native Orca worker dispatch for supported agents (claude, codex, antigravity)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pab.core.orca_bridge")

# Agents natively recognized by Orca ADE worker-start
ORCA_NATIVE_AGENTS = {
    "claude",
    "codex",
    "cursor",
    "antigravity",
    "agy",
    "muse",
    "zcode",
    "opencode",
    "opencode2",
}


def resolve_orca_cli() -> Optional[str]:
    """
    Resolve the authoritative Orca CLI binary for this environment.
    Rule:
    1. If ORCA_CLI_COMMAND is set, use it.
    2. Dev repo root: orca-dev.
    3. On Linux outside Orca terminal: prefer orca-ide to avoid GNOME speech reader.
    4. Otherwise orca.
    """
    env_cmd = os.environ.get("ORCA_CLI_COMMAND")
    if env_cmd:
        return env_cmd

    candidates = [
        "/root/.config/orca/cli/bin/orca-ide",
        shutil.which("orca-ide"),
        "/root/.config/orca/cli/bin/orca",
        shutil.which("orca"),
    ]
    for c in candidates:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


class OrcaBridge:
    """Interoperability bridge with Orca ADE Orchestration."""

    def __init__(self, cli_path: Optional[str] = None):
        self._cli_path = cli_path or resolve_orca_cli()

    @property
    def is_available(self) -> bool:
        return bool(self._cli_path)

    @property
    def cli_path(self) -> Optional[str]:
        return self._cli_path

    def _run_cmd(self, args: List[str], timeout: float = 15.0) -> Dict[str, Any]:
        """Execute an Orca CLI command with --json framing and parse result."""
        if not self._cli_path:
            return {"ok": False, "error": "Orca CLI executable not found on system"}

        full_cmd = [self._cli_path] + args
        if "--json" not in full_cmd:
            full_cmd.append("--json")

        try:
            proc = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = proc.stdout.strip()
            if stdout:
                try:
                    data = json.loads(stdout)
                    return data
                except Exception:
                    pass
            return {
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": proc.stderr.strip(),
            }
        except Exception as exc:
            logger.warning("Error running Orca CLI %s: %s", args, exc)
            return {"ok": False, "error": str(exc)}

    # -------------------------------------------------------------------------
    # Worktree Discovery
    # -------------------------------------------------------------------------
    def list_worktrees(self) -> List[Dict[str, Any]]:
        """List active Orca worktrees."""
        res = self._run_cmd(["worktree", "list"])
        if res.get("ok"):
            return res.get("result", {}).get("worktrees", [])
        return []

    def get_worktree_for_path(self, target_path: Path) -> Optional[Dict[str, Any]]:
        """Find the Orca worktree corresponding to a filesystem path."""
        target_resolved = str(Path(target_path).resolve())
        for wt in self.list_worktrees():
            wt_path = wt.get("path")
            if wt_path and str(Path(wt_path).resolve()) == target_resolved:
                return wt
        return None

    # -------------------------------------------------------------------------
    # Orchestration Runs
    # -------------------------------------------------------------------------
    def create_run(self, objective: str) -> Optional[Dict[str, Any]]:
        """Create and bind a lightweight Orca orchestration Run."""
        res = self._run_cmd(["orchestration", "run-create", "--objective", objective])
        if res.get("ok"):
            return res.get("result", {})
        return None

    def list_runs(self) -> List[Dict[str, Any]]:
        """List active and historical Orca Runs."""
        res = self._run_cmd(["orchestration", "run-list"])
        if res.get("ok"):
            return res.get("result", {}).get("runs", [])
        return []

    # -------------------------------------------------------------------------
    # Inter-Agent Messaging & Hybrid Pi Bridge
    # -------------------------------------------------------------------------
    def send_message(
        self,
        subject: str,
        run_id: Optional[str] = None,
        msg_type: str = "status",
        body: Optional[str] = None,
        task_id: Optional[str] = None,
        dispatch_id: Optional[str] = None,
        outcome: Optional[str] = None,
        to_target: Optional[str] = None,
    ) -> bool:
        """Send an inter-agent orchestration message."""
        args = ["orchestration", "send", "--subject", subject, "--type", msg_type]
        if run_id:
            args.extend(["--run", run_id])
        if body:
            args.extend(["--body", body])
        if task_id:
            args.extend(["--task-id", task_id])
        if dispatch_id:
            args.extend(["--dispatch-id", dispatch_id])
        if outcome:
            args.extend(["--outcome", outcome])
        if to_target:
            args.extend(["--to", to_target])

        res = self._run_cmd(args)
        return bool(res.get("ok"))

    def send_worker_done(
        self,
        run_id: str,
        task_id: str,
        dispatch_id: str,
        outcome: str = "succeeded",
        report_path: Optional[str] = None,
    ) -> bool:
        """
        Notify Orca that a supervised worker (e.g., Pi settled) has completed.
        This provides parity for non-native agents in Orca.
        """
        args = [
            "orchestration",
            "send",
            "--subject",
            f"Worker done: {task_id}",
            "--type",
            "worker_done",
            "--run",
            run_id,
            "--task-id",
            task_id,
            "--dispatch-id",
            dispatch_id,
            "--outcome",
            outcome,
        ]
        if report_path:
            args.extend(["--report-path", report_path])
        res = self._run_cmd(args)
        return bool(res.get("ok"))

    def send_heartbeat(self, run_id: str, task_id: str, dispatch_id: str) -> bool:
        """Send heartbeat message to keep dispatch alive in Orca."""
        return self.send_message(
            subject=f"Heartbeat: {task_id}",
            run_id=run_id,
            msg_type="heartbeat",
            task_id=task_id,
            dispatch_id=dispatch_id,
        )

    # -------------------------------------------------------------------------
    # Worker Dispatch Check
    # -------------------------------------------------------------------------
    def is_orca_native_agent(self, agent_name: str) -> bool:
        """Check if Orca ADE supports native worker-start for this agent."""
        return agent_name.lower() in ORCA_NATIVE_AGENTS

    def start_native_worker(
        self,
        spec: str,
        agent: str,
        run_id: Optional[str] = None,
        worktree_selector: Optional[str] = None,
        task_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch a native agent via Orca's worker-start."""
        args = [
            "orchestration",
            "worker-start",
            "--spec",
            spec,
            "--agent",
            agent,
        ]
        if run_id:
            args.extend(["--run", run_id])
        if worktree_selector:
            args.extend(["--worktree", worktree_selector])
        if task_title:
            args.extend(["--task-title", task_title])

        return self._run_cmd(args)
