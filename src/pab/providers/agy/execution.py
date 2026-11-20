"""Real AGY subprocess execution, result capture and failure handling.

Runs the Google Antigravity CLI in *print mode* (non-interactive, single turn) with an
isolated profile HOME, captures the machine-readable JSON result, and normalises it into
an :class:`AgyExecutionResult`.

Failure modes are explicit — nothing is ever reported as a success unless AGY really
exited cleanly and returned a usable, traceable result:

* executable missing
* workdir / profile home missing
* timeout (process group is terminated)
* non-zero exit code
* unparsable / invalid JSON payload
* AGY status != SUCCESS
* empty response or missing conversation id (trace id)
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from pab.providers.agy.config import get_agy_bin
from pab.providers.agy.workers import AgyWorkerProfile


@dataclass
class AgyExecutionResult:
    """Normalised outcome of a single AGY execution."""

    ok: bool
    worker_id: str
    profile: str
    profile_home: str
    workdir: str
    conversation_id: Optional[str] = None
    status: Optional[str] = None
    response: str = ""
    duration_seconds: float = 0.0
    num_turns: Optional[int] = None
    usage: Dict[str, Any] = field(default_factory=dict)
    exit_code: Optional[int] = None
    trace_path: Optional[str] = None
    profile_log: Optional[str] = None
    error: Optional[str] = None
    stdout_tail: str = ""
    stderr_tail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "worker_id": self.worker_id,
            "profile": self.profile,
            "profile_home": self.profile_home,
            "workdir": self.workdir,
            "conversation_id": self.conversation_id,
            "status": self.status,
            "response": self.response,
            "duration_seconds": self.duration_seconds,
            "num_turns": self.num_turns,
            "usage": self.usage,
            "exit_code": self.exit_code,
            "trace_path": self.trace_path,
            "profile_log": self.profile_log,
            "error": self.error,
        }


class AgyRunner:
    """Executes AGY print-mode turns against an isolated AGY profile."""

    def __init__(
        self,
        executable_path: Optional[str] = None,
        default_timeout: float = 900.0,
        skip_permissions: bool = True,
    ):
        self._executable_path = executable_path
        self._default_timeout = default_timeout
        self._skip_permissions = skip_permissions

    @property
    def default_timeout(self) -> float:
        return self._default_timeout

    # -- helpers -----------------------------------------------------------
    def resolve_executable(self) -> Optional[str]:
        if self._executable_path:
            return self._executable_path
        return get_agy_bin()

    def build_command(self, prompt: str) -> List[str]:
        """
        Build the AGY argument vector.

        ``--output-format`` must precede ``--print``: ``--print`` swallows the next
        token as its prompt.
        """
        cmd = [self.resolve_executable() or "agy", "--output-format", "json"]
        if self._skip_permissions:
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--print", prompt])
        return cmd

    def build_env(self, profile_home: Path, extra_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build the child environment with the AGY profile HOME applied."""
        env = os.environ.copy()
        home = Path(profile_home).expanduser()
        env["HOME"] = str(home)
        env["GEMINI_CONFIG_DIR"] = str(home / ".gemini" / "config")
        env["PAB_HOME"] = str(Path.home() / ".pab")
        local_bin = str(Path.home() / ".local" / "bin")
        env["PATH"] = f"{local_bin}{os.pathsep}{env.get('PATH', '')}"
        if extra_env:
            env.update({str(k): str(v) for k, v in extra_env.items()})
        return env

    # -- execution ---------------------------------------------------------
    def run(
        self,
        worker: AgyWorkerProfile,
        prompt: str,
        timeout: Optional[float] = None,
        extra_env: Optional[Dict[str, str]] = None,
        workdir: Optional[Path] = None,
    ) -> AgyExecutionResult:
        """Execute a single AGY turn and return the normalised result."""
        timeout = float(timeout or self._default_timeout)
        started = time.time()

        def fail(error: str, **kwargs: Any) -> AgyExecutionResult:
            return AgyExecutionResult(
                ok=False,
                worker_id=worker.worker_id,
                profile=worker.profile,
                profile_home=str(worker.profile_home),
                workdir=str(worker.workdir),
                duration_seconds=round(time.time() - started, 3),
                error=error,
                **kwargs,
            )

        if not prompt or not prompt.strip():
            return fail("Refusing to execute AGY with an empty prompt.")

        executable = self.resolve_executable()
        if not executable:
            return fail("AGY executable not found on PATH or in ~/.local/bin.")

        workdir = Path(workdir).expanduser() if workdir else Path(worker.workdir).expanduser()
        if not workdir.is_dir():
            return fail(f"AGY workdir does not exist: {workdir}")

        profile_home = Path(worker.profile_home).expanduser()
        if not profile_home.is_dir():
            return fail(f"AGY profile home does not exist: {profile_home}")

        cmd = self.build_command(prompt)
        env = self.build_env(profile_home, extra_env)

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(workdir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
        except Exception as exc:
            return fail(f"Failed to start AGY process: {exc}")

        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            stdout, stderr = self._terminate(proc)

        duration = round(time.time() - started, 3)
        stdout = stdout or ""
        stderr = stderr or ""

        profile_log = self._newest_profile_log(profile_home, since=started)

        if timed_out:
            return AgyExecutionResult(
                ok=False,
                worker_id=worker.worker_id,
                profile=worker.profile,
                profile_home=str(profile_home),
                workdir=str(workdir),
                duration_seconds=duration,
                exit_code=proc.returncode,
                profile_log=profile_log,
                error=f"AGY execution timed out after {timeout}s",
                stdout_tail=stdout[-2000:],
                stderr_tail=stderr[-2000:],
            )

        if proc.returncode != 0:
            return AgyExecutionResult(
                ok=False,
                worker_id=worker.worker_id,
                profile=worker.profile,
                profile_home=str(profile_home),
                workdir=str(workdir),
                duration_seconds=duration,
                exit_code=proc.returncode,
                profile_log=profile_log,
                error=f"AGY exited with non-zero status {proc.returncode}",
                stdout_tail=stdout[-2000:],
                stderr_tail=stderr[-2000:],
            )

        payload = self._extract_json(stdout)
        if payload is None:
            return AgyExecutionResult(
                ok=False,
                worker_id=worker.worker_id,
                profile=worker.profile,
                profile_home=str(profile_home),
                workdir=str(workdir),
                duration_seconds=duration,
                exit_code=proc.returncode,
                profile_log=profile_log,
                error="AGY returned no parsable JSON result",
                stdout_tail=stdout[-2000:],
                stderr_tail=stderr[-2000:],
            )

        status = payload.get("status")
        response = payload.get("response") or ""
        conversation_id = payload.get("conversation_id")

        result = AgyExecutionResult(
            ok=True,
            worker_id=worker.worker_id,
            profile=worker.profile,
            profile_home=str(profile_home),
            workdir=str(workdir),
            conversation_id=conversation_id,
            status=status,
            response=response,
            duration_seconds=duration,
            num_turns=payload.get("num_turns"),
            usage=payload.get("usage") or {},
            exit_code=proc.returncode,
            profile_log=profile_log,
            stdout_tail=stdout[-2000:],
            stderr_tail=stderr[-2000:],
        )

        # Validity gate: a "success" requires a real, traceable AGY result.
        if status != "SUCCESS":
            result.ok = False
            result.error = f"AGY reported status '{status}' instead of 'SUCCESS'"
            return result
        if not conversation_id:
            result.ok = False
            result.error = "AGY result did not contain a conversation_id (trace id)"
            return result
        if not response.strip():
            result.ok = False
            result.error = "AGY returned an empty response"
            return result

        result.trace_path = self._locate_trace(profile_home, conversation_id)
        return result

    # -- internals ---------------------------------------------------------
    def _terminate(self, proc: "subprocess.Popen[str]") -> tuple[str, str]:
        """Terminate the whole AGY process group and drain its pipes."""
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            stdout, stderr = proc.communicate(timeout=10)
            return stdout or "", stderr or ""
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                stdout, stderr = proc.communicate(timeout=5)
                return stdout or "", stderr or ""
            except Exception:
                return "", ""

    @staticmethod
    def _extract_json(stdout: str) -> Optional[Dict[str, Any]]:
        """Extract the AGY result object from stdout (banner lines may precede it)."""
        text = (stdout or "").strip()
        if not text:
            return None

        candidates = [text]
        candidates.extend([ln.strip() for ln in reversed(text.splitlines()) if ln.strip().startswith("{")])

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list) and parsed and isinstance(parsed[-1], dict):
                return parsed[-1]
        return None

    @staticmethod
    def _locate_trace(profile_home: Path, conversation_id: str) -> Optional[str]:
        """Locate the AGY transcript (trace) file for a conversation, if present."""
        brain = Path(profile_home).expanduser() / ".gemini" / "antigravity-cli" / "brain" / conversation_id
        direct = brain / ".system_generated" / "logs" / "transcript.jsonl"
        if direct.is_file():
            return str(direct)
        try:
            matches = sorted(brain.rglob("transcript.jsonl"))
            if matches:
                return str(matches[0])
        except Exception:
            pass
        return None

    @staticmethod
    def _newest_profile_log(profile_home: Path, since: float) -> Optional[str]:
        """Return the newest AGY CLI log written under the profile home since `since`.

        This is on-disk evidence that the process really ran with the expected
        profile HOME (profile isolation), not the shared default profile.
        """
        log_dir = Path(profile_home).expanduser() / ".gemini" / "antigravity-cli" / "log"
        if not log_dir.is_dir():
            return None
        newest: Optional[Path] = None
        newest_ts = 0.0
        try:
            for entry in log_dir.iterdir():
                if not entry.is_file():
                    continue
                ts = entry.stat().st_mtime
                if ts >= since - 1 and ts >= newest_ts:
                    newest = entry
                    newest_ts = ts
        except Exception:
            return None
        return str(newest) if newest else None
