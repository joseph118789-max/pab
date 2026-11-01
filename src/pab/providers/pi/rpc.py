"""Pi Coding Agent RPC client and protocol manager.

Manages long-lived `pi --mode rpc` subprocesses via bidirectional JSONL over stdin/stdout.
Tracks request-response correlation, handles binary LF framing, decodes streaming events,
and ensures completion on `agent_settled`.
"""

from __future__ import annotations

import collections
import concurrent.futures
import json
import logging
import os
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterator, List, Optional

logger = logging.getLogger("pab.providers.pi.rpc")


class PiRpcError(Exception):
    """Raised when Pi RPC returns a failure response or encounters a protocol error."""

    def __init__(self, message: str, raw_response: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.raw_response = raw_response or {}


class PiRpcClient:
    """Subprocess manager for `pi --mode rpc`."""

    def __init__(
        self,
        executable_path: str,
        workspace_path: Path,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        append_system_prompt: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ):
        self.executable_path = executable_path
        self.workspace_path = Path(workspace_path).resolve()
        self.session_id = session_id
        self.model = model
        self.append_system_prompt = append_system_prompt
        self.extra_args = extra_args or []
        self.env = env or {}

        self.proc: Optional[subprocess.Popen] = None
        self._pending_commands: Dict[str, concurrent.futures.Future[Dict[str, Any]]] = {}
        self._event_listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.Lock()

        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._stderr_lines: Deque[str] = collections.deque(maxlen=200)

        self._settle_event = threading.Event()
        self._is_active_run: bool = False
        self._is_closed: bool = False
        self._last_assistant_text: str = ""
        self._captured_events: List[Dict[str, Any]] = []

    def start(self) -> None:
        """Spawn the `pi --mode rpc` child process and start IO reader threads."""
        if self.executable_path.endswith(".py"):
            cmd = ["python3", self.executable_path]
        else:
            cmd = [self.executable_path, "--mode", "rpc"]

        if self.session_id:
            cmd.extend(["--session-id", self.session_id])

        if self.model:
            cmd.extend(["--model", self.model])

        if self.append_system_prompt:
            cmd.extend(["--append-system-prompt", self.append_system_prompt])

        cmd.extend(self.extra_args)

        full_env = os.environ.copy()
        full_env.update(self.env)

        logger.debug("Starting Pi RPC subprocess: %s in %s", cmd, self.workspace_path)
        self.proc = subprocess.Popen(
            cmd,
            cwd=str(self.workspace_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=full_env,
            bufsize=0,  # Unbuffered binary pipes
        )

        self._settle_event.set()  # Initial state: settled/idle

        # Start background reader threads
        self._stdout_thread = threading.Thread(
            target=self._read_stdout_loop,
            name=f"pi-rpc-stdout-{self.proc.pid}",
            daemon=True,
        )
        self._stdout_thread.start()

        self._stderr_thread = threading.Thread(
            target=self._read_stderr_loop,
            name=f"pi-rpc-stderr-{self.proc.pid}",
            daemon=True,
        )
        self._stderr_thread.start()

    @property
    def pid(self) -> Optional[int]:
        return self.proc.pid if self.proc else None

    @property
    def is_alive(self) -> bool:
        if not self.proc:
            return False
        return self.proc.poll() is None

    @property
    def is_running(self) -> bool:
        """Return True if an agent run/turn is actively executing."""
        return self._is_active_run and self.is_alive

    def add_event_listener(self, listener: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for streaming Pi session events."""
        with self._lock:
            self._event_listeners.append(listener)

    def remove_event_listener(self, listener: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            if listener in self._event_listeners:
                self._event_listeners.remove(listener)

    def _read_stdout_loop(self) -> None:
        """
        Continuously read stdout binary stream, strictly splitting on LF (0x0A).
        Prevents parser errors on Unicode paragraph separators inside JSON.
        """
        assert self.proc and self.proc.stdout
        raw_stream = self.proc.stdout
        buf = bytearray()

        while True:
            chunk = raw_stream.read(4096)
            if not chunk:
                break
            buf.extend(chunk)

            while b"\n" in buf:
                line_bytes, _, remaining = buf.partition(b"\n")
                buf = bytearray(remaining)

                # Strip trailing CR if present
                if line_bytes.endswith(b"\r"):
                    line_bytes = line_bytes[:-1]

                line_str = line_bytes.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    record = json.loads(line_str)
                    self._dispatch_record(record)
                except Exception as exc:
                    logger.warning("Failed to decode JSONL line from Pi RPC: %s (err: %s)", line_str, exc)

        # Process exited or stdout closed
        self._cleanup_pending_commands(PiRpcError("Pi RPC process stdout closed unexpectedly"))

    def _read_stderr_loop(self) -> None:
        """Drains stderr into in-memory ring buffer to prevent pipe deadlock."""
        assert self.proc and self.proc.stderr
        for line in self.proc.stderr:
            decoded = line.decode("utf-8", errors="replace").strip()
            if decoded:
                self._stderr_lines.append(decoded)
                logger.debug("[Pi stderr] %s", decoded)

    def _dispatch_record(self, record: Dict[str, Any]) -> None:
        """Process incoming JSONL protocol records from Pi."""
        record_type = record.get("type")

        # 1. Command Response record
        if record_type == "response":
            req_id = record.get("id")
            if req_id:
                with self._lock:
                    future = self._pending_commands.pop(req_id, None)
                if future and not future.done():
                    if record.get("success"):
                        future.set_result(record.get("data", {}))
                    else:
                        future.set_exception(PiRpcError(record.get("error", "RPC command failed"), record))
            return

        # 2. Extension UI Request (auto-acknowledge or silently record)
        if record_type == "extension_ui_request":
            ui_id = record.get("id")
            # If Pi expects a response, respond with null/empty to allow Pi to proceed
            if ui_id:
                resp = {"type": "extension_ui_response", "id": ui_id, "data": None}
                self._send_raw(resp)
            return

        # 3. Session Events
        self._captured_events.append(record)

        if record_type == "agent_start":
            self._is_active_run = True
            self._settle_event.clear()

        elif record_type == "message_update":
            update = record.get("assistantMessageEvent", {})
            if update.get("type") == "text_delta":
                self._last_assistant_text += update.get("delta", "")

        elif record_type == "agent_settled":
            self._is_active_run = False
            self._settle_event.set()

        # Notify external listeners
        with self._lock:
            listeners = list(self._event_listeners)
        for listener in listeners:
            try:
                listener(record)
            except Exception as exc:
                logger.exception("Error in Pi event listener callback: %s", exc)

    def _send_raw(self, payload: Dict[str, Any]) -> None:
        """Serialize payload to JSON and write to stdin followed by LF."""
        if not self.proc or not self.proc.stdin:
            raise PiRpcError("Pi RPC process stdin is not open")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
        try:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise PiRpcError(f"Failed writing to Pi stdin: {exc}")

    def send_command(
        self,
        command_type: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Send a correlated command and await its matching response."""
        if not self.is_alive:
            stderr_dump = "\n".join(list(self._stderr_lines)[-5:])
            raise PiRpcError(f"Pi RPC process is dead. Stderr:\n{stderr_dump}")

        req_id = f"pab-cmd-{uuid.uuid4().hex[:12]}"
        cmd_dict = {"id": req_id, "type": command_type}
        if payload:
            cmd_dict.update(payload)

        future: concurrent.futures.Future[Dict[str, Any]] = concurrent.futures.Future()
        with self._lock:
            self._pending_commands[req_id] = future

        self._send_raw(cmd_dict)

        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            with self._lock:
                self._pending_commands.pop(req_id, None)
            raise PiRpcError(f"Command '{command_type}' timed out after {timeout}s")

    def prompt(self, message: str, timeout: float = 300.0) -> Dict[str, Any]:
        """
        Send a prompt to Pi and wait for the run to emit `agent_settled`.
        Guarantees that all automatic retries, tool execution, and compaction finish.
        """
        self._last_assistant_text = ""
        self._settle_event.clear()
        self._is_active_run = True

        res = self.send_command("prompt", {"message": message}, timeout=30.0)
        disposition = res.get("disposition")

        # If Pi handled the prompt synchronously without starting an agent turn
        if disposition == "handled":
            self._is_active_run = False
            self._settle_event.set()
            return {"disposition": "handled", "text": self._last_assistant_text}

        # Await agent_settled
        settled = self._settle_event.wait(timeout=timeout)
        if not settled:
            raise PiRpcError(f"Pi prompt execution timed out after {timeout}s waiting for agent_settled")

        return {
            "disposition": disposition or "settled",
            "text": self._last_assistant_text,
            "session_id": self.session_id,
        }

    def abort(self) -> Dict[str, Any]:
        """Abort currently running agent turn."""
        return self.send_command("abort", timeout=10.0)

    def get_state(self) -> Dict[str, Any]:
        """Fetch current session state from Pi."""
        return self.send_command("get_state", timeout=10.0)

    def get_messages(self) -> List[Dict[str, Any]]:
        """Fetch message tree / conversation entries."""
        res = self.send_command("get_messages", timeout=10.0)
        return res.get("messages", [])

    def new_session(self) -> Dict[str, Any]:
        """Initialize a new session in Pi."""
        return self.send_command("new_session", timeout=10.0)

    def set_model(self, model: str) -> Dict[str, Any]:
        """Dynamically switch model provider pattern."""
        return self.send_command("set_model", {"model": model}, timeout=10.0)

    def wait_for_settled(self, timeout: float = 300.0) -> bool:
        """Block until the active turn emits `agent_settled`."""
        return self._settle_event.wait(timeout=timeout)

    def _cleanup_pending_commands(self, exc: Exception) -> None:
        with self._lock:
            for fut in self._pending_commands.values():
                if not fut.done():
                    fut.set_exception(exc)
            self._pending_commands.clear()

    def close(self, force: bool = False, timeout: float = 5.0) -> None:
        """Orderly shutdown: send abort, close stdin, wait, SIGTERM, SIGKILL."""
        if self._is_closed:
            return
        self._is_closed = True

        if self.proc and self.is_alive:
            try:
                if self._is_active_run:
                    self.abort()
            except Exception:
                pass

            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
            except Exception:
                pass

            try:
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning("Pi RPC process did not exit gracefully; issuing SIGTERM")
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    if force:
                        logger.warning("Pi RPC process ignored SIGTERM; issuing SIGKILL")
                        self.proc.kill()
                        self.proc.wait(timeout=1.0)

        self._cleanup_pending_commands(PiRpcError("Pi RPC client closed"))
