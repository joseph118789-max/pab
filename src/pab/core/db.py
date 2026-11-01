"""SQLite storage layer for PAB registry and audit trail."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pab.core.models.execution import (
    ExecutionEvent,
    ExecutionHandle,
    ExecutionMode,
    ExecutionStatus,
)
from pab.core.models.orchestration import (
    DecisionGate,
    DispatchStatus,
    GateStatus,
    OrchestrationDispatch,
    OrchestrationMessage,
    OrchestrationRun,
    OrchestrationTask,
    RunStatus,
    TaskStatus,
)


class Database:
    """Manages SQLite tables and transactions for PAB."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    schema_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    schema_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    commit_message TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS skills (
                    name TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    path TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    source_provider TEXT,
                    source_path TEXT,
                    project_id TEXT,
                    agent_id TEXT,
                    untrusted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    source_provider TEXT NOT NULL,
                    source_session_id TEXT NOT NULL,
                    project TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    exported_at TEXT NOT NULL,
                    data_json TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    provider TEXT,
                    details_json TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_plans (
                    plan_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    approved INTEGER NOT NULL DEFAULT 0,
                    applied INTEGER NOT NULL DEFAULT 0,
                    plan_json TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS switch_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    handoff_id TEXT NOT NULL UNIQUE,
                    source_provider TEXT NOT NULL,
                    target_provider TEXT NOT NULL,
                    source_session_id TEXT,
                    source_agent_id TEXT,
                    project_path TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    skills_synced_json TEXT,
                    warnings_json TEXT,
                    manifest_json TEXT,
                    launched INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE NOT NULL,
                    task_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    worker_profile_version INTEGER NOT NULL DEFAULT 1,
                    execution_generation INTEGER NOT NULL DEFAULT 1,
                    provider TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    workspace TEXT NOT NULL,
                    status TEXT NOT NULL,
                    native_session_id TEXT,
                    process_id INTEGER,
                    terminal_handle TEXT,
                    exit_code INTEGER,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    last_event_sequence INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    metadata_json TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_events (
                    event_id TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    execution_generation INTEGER NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload_json TEXT,
                    UNIQUE (execution_id, sequence_number)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    workspace_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    coordinator_agent TEXT,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    spec TEXT NOT NULL,
                    dependencies_json TEXT,
                    status TEXT NOT NULL,
                    assigned_worker_id TEXT,
                    gate_id TEXT,
                    personaos_task_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS dispatches (
                    dispatch_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    agent_provider TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    worktree_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    terminal_handle TEXT,
                    process_id INTEGER,
                    attempt_number INTEGER NOT NULL DEFAULT 1,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    result_summary TEXT,
                    metadata_json TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_gates (
                    gate_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    options_json TEXT,
                    status TEXT NOT NULL,
                    resolution TEXT,
                    resolved_by TEXT,
                    resolved_at TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS orchestration_messages (
                    message_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    thread_id TEXT,
                    from_handle TEXT NOT NULL,
                    to_target TEXT,
                    msg_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT,
                    payload_json TEXT,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def record_audit(
        self,
        event_type: str,
        resource_type: str,
        resource_id: str,
        provider: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert an audit log entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_log (timestamp, event_type, resource_type, resource_id, provider, details_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    event_type,
                    resource_type,
                    resource_id,
                    provider,
                    json.dumps(details or {}),
                ),
            )
            conn.commit()

    def get_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def record_switch(self, record: Dict[str, Any]) -> None:
        """Insert or update a switch history entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO switch_history (
                    handoff_id, source_provider, target_provider, source_session_id,
                    source_agent_id, project_path, mode, skills_synced_json,
                    warnings_json, manifest_json, launched, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["handoff_id"],
                    record["source_provider"],
                    record["target_provider"],
                    record.get("source_session_id"),
                    record.get("source_agent_id"),
                    record["project_path"],
                    record.get("mode", "handoff"),
                    json.dumps(record.get("skills_synced", [])),
                    json.dumps(record.get("warnings", [])),
                    json.dumps(record.get("manifest", {})),
                    1 if record.get("launched") else 0,
                    record.get("created_at") or datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def get_switch_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM switch_history ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_switch_by_handoff(self, handoff_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM switch_history WHERE handoff_id = ?",
                (handoff_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_execution(self, handle: ExecutionHandle) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO executions (
                    execution_id, request_id, idempotency_key, task_id, worker_id,
                    worker_profile_version, execution_generation, provider, execution_mode,
                    workspace, status, native_session_id, process_id, terminal_handle,
                    exit_code, started_at, completed_at, last_event_sequence, error_message, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    handle.execution_id,
                    handle.request_id,
                    handle.idempotency_key,
                    handle.task_id,
                    handle.worker_id,
                    handle.worker_profile_version,
                    handle.execution_generation,
                    handle.provider,
                    handle.execution_mode.value,
                    handle.workspace,
                    handle.status.value,
                    handle.native_session_id,
                    handle.process_id,
                    handle.terminal_handle,
                    handle.exit_code,
                    handle.started_at.isoformat(),
                    handle.completed_at.isoformat() if handle.completed_at else None,
                    handle.last_event_sequence,
                    handle.error_message,
                    json.dumps(handle.metadata),
                ),
            )
            conn.commit()

    def update_execution(self, handle: ExecutionHandle) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE executions SET
                    status = ?,
                    native_session_id = ?,
                    process_id = ?,
                    terminal_handle = ?,
                    exit_code = ?,
                    completed_at = ?,
                    last_event_sequence = ?,
                    error_message = ?,
                    metadata_json = ?
                WHERE execution_id = ?
                """,
                (
                    handle.status.value,
                    handle.native_session_id,
                    handle.process_id,
                    handle.terminal_handle,
                    handle.exit_code,
                    handle.completed_at.isoformat() if handle.completed_at else None,
                    handle.last_event_sequence,
                    handle.error_message,
                    json.dumps(handle.metadata),
                    handle.execution_id,
                ),
            )
            conn.commit()

    def get_execution(self, execution_id: str) -> Optional[ExecutionHandle]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM executions WHERE execution_id = ?", (execution_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_execution_handle(row)

    def get_execution_by_idempotency_key(self, idempotency_key: str) -> Optional[ExecutionHandle]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM executions WHERE idempotency_key = ?", (idempotency_key,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_execution_handle(row)

    def list_executions(self, status: Optional[str] = None, provider: Optional[str] = None) -> List[ExecutionHandle]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM executions WHERE 1=1"
            params: List[Any] = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if provider:
                query += " AND provider = ?"
                params.append(provider)
            query += " ORDER BY started_at DESC"
            cursor.execute(query, tuple(params))
            return [self._row_to_execution_handle(row) for row in cursor.fetchall()]

    def _row_to_execution_handle(self, row: sqlite3.Row) -> ExecutionHandle:
        d = dict(row)
        metadata = json.loads(d.get("metadata_json") or "{}")
        d["metadata"] = metadata
        return ExecutionHandle.from_dict(d)

    def save_event(self, event: ExecutionEvent) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO execution_events (
                    event_id, execution_id, request_id, execution_generation,
                    sequence_number, event_type, timestamp, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.execution_id,
                    event.request_id,
                    event.execution_generation,
                    event.sequence_number,
                    event.event_type,
                    event.timestamp.isoformat(),
                    json.dumps(event.payload),
                ),
            )
            cursor.execute(
                """
                UPDATE executions SET last_event_sequence = MAX(last_event_sequence, ?)
                WHERE execution_id = ?
                """,
                (event.sequence_number, event.execution_id),
            )
            conn.commit()

    def list_events(self, execution_id: str, since_sequence: int = 0) -> List[ExecutionEvent]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM execution_events
                WHERE execution_id = ? AND sequence_number > ?
                ORDER BY sequence_number ASC
                """,
                (execution_id, since_sequence),
            )
            events = []
            for row in cursor.fetchall():
                d = dict(row)
                d["payload"] = json.loads(d.get("payload_json") or "{}")
                events.append(ExecutionEvent.from_dict(d))
            return events

    def get_next_sequence_number(self, execution_id: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM execution_events WHERE execution_id = ?",
                (execution_id,),
            )
            return cursor.fetchone()[0]

    # -------------------------------------------------------------------------
    # Orchestration Runs, Tasks, Dispatches, Gates & Messages
    # -------------------------------------------------------------------------
    def save_run(self, run: OrchestrationRun) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO runs (
                    run_id, name, objective, workspace_path, status, coordinator_agent, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.name,
                    run.objective,
                    run.workspace_path,
                    run.status.value,
                    run.coordinator_agent,
                    run.created_at.isoformat(),
                    json.dumps(run.metadata),
                ),
            )
            conn.commit()

    def get_run(self, run_id: str) -> Optional[OrchestrationRun]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
            return OrchestrationRun.from_dict(d)

    def list_runs(self, status: Optional[str] = None) -> List[OrchestrationRun]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM runs WHERE status = ? ORDER BY created_at DESC", (status,))
            else:
                cursor.execute("SELECT * FROM runs ORDER BY created_at DESC")
            runs = []
            for row in cursor.fetchall():
                d = dict(row)
                d["metadata"] = json.loads(d.get("metadata_json") or "{}")
                runs.append(OrchestrationRun.from_dict(d))
            return runs

    def save_task(self, task: OrchestrationTask) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO tasks (
                    task_id, run_id, title, spec, dependencies_json, status, assigned_worker_id, gate_id, personaos_task_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.run_id,
                    task.title,
                    task.spec,
                    json.dumps(task.dependencies),
                    task.status.value,
                    task.assigned_worker_id,
                    task.gate_id,
                    task.personaos_task_id,
                    task.created_at.isoformat(),
                ),
            )
            conn.commit()

    def get_task(self, task_id: str) -> Optional[OrchestrationTask]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["dependencies"] = json.loads(d.get("dependencies_json") or "[]")
            return OrchestrationTask.from_dict(d)

    def list_tasks(self, run_id: Optional[str] = None) -> List[OrchestrationTask]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if run_id:
                cursor.execute("SELECT * FROM tasks WHERE run_id = ? ORDER BY created_at ASC", (run_id,))
            else:
                cursor.execute("SELECT * FROM tasks ORDER BY created_at ASC")
            tasks = []
            for row in cursor.fetchall():
                d = dict(row)
                d["dependencies"] = json.loads(d.get("dependencies_json") or "[]")
                tasks.append(OrchestrationTask.from_dict(d))
            return tasks

    def save_dispatch(self, dispatch: OrchestrationDispatch) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO dispatches (
                    dispatch_id, task_id, run_id, agent_provider, worker_id, worktree_path,
                    status, terminal_handle, process_id, attempt_number, started_at, completed_at,
                    result_summary, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dispatch.dispatch_id,
                    dispatch.task_id,
                    dispatch.run_id,
                    dispatch.agent_provider,
                    dispatch.worker_id,
                    dispatch.worktree_path,
                    dispatch.status.value,
                    dispatch.terminal_handle,
                    dispatch.process_id,
                    dispatch.attempt_number,
                    dispatch.started_at.isoformat(),
                    dispatch.completed_at.isoformat() if dispatch.completed_at else None,
                    dispatch.result_summary,
                    json.dumps(dispatch.metadata),
                ),
            )
            conn.commit()

    def get_dispatch(self, dispatch_id: str) -> Optional[OrchestrationDispatch]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dispatches WHERE dispatch_id = ?", (dispatch_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
            return OrchestrationDispatch.from_dict(d)

    def list_dispatches(self, run_id: Optional[str] = None, task_id: Optional[str] = None) -> List[OrchestrationDispatch]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if run_id and task_id:
                cursor.execute("SELECT * FROM dispatches WHERE run_id = ? AND task_id = ? ORDER BY started_at ASC", (run_id, task_id))
            elif run_id:
                cursor.execute("SELECT * FROM dispatches WHERE run_id = ? ORDER BY started_at ASC", (run_id,))
            elif task_id:
                cursor.execute("SELECT * FROM dispatches WHERE task_id = ? ORDER BY started_at ASC", (task_id,))
            else:
                cursor.execute("SELECT * FROM dispatches ORDER BY started_at ASC")
            dispatches = []
            for row in cursor.fetchall():
                d = dict(row)
                d["metadata"] = json.loads(d.get("metadata_json") or "{}")
                dispatches.append(OrchestrationDispatch.from_dict(d))
            return dispatches

    def save_decision_gate(self, gate: DecisionGate) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO decision_gates (
                    gate_id, task_id, question, options_json, status, resolution, resolved_by, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gate.gate_id,
                    gate.task_id,
                    gate.question,
                    json.dumps(gate.options),
                    gate.status.value,
                    gate.resolution,
                    gate.resolved_by,
                    gate.resolved_at.isoformat() if gate.resolved_at else None,
                ),
            )
            conn.commit()

    def get_decision_gate(self, gate_id: str) -> Optional[DecisionGate]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM decision_gates WHERE gate_id = ?", (gate_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["options"] = json.loads(d.get("options_json") or '["approve", "reject"]')
            return DecisionGate.from_dict(d)

    def list_decision_gates(self, task_id: Optional[str] = None) -> List[DecisionGate]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if task_id:
                cursor.execute("SELECT * FROM decision_gates WHERE task_id = ?", (task_id,))
            else:
                cursor.execute("SELECT * FROM decision_gates")
            gates = []
            for row in cursor.fetchall():
                d = dict(row)
                d["options"] = json.loads(d.get("options_json") or '["approve", "reject"]')
                gates.append(DecisionGate.from_dict(d))
            return gates

    def save_message(self, msg: OrchestrationMessage) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO orchestration_messages (
                    message_id, run_id, thread_id, from_handle, to_target, msg_type, subject, body, payload_json, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg.message_id,
                    msg.run_id,
                    msg.thread_id,
                    msg.from_handle,
                    msg.to_target,
                    msg.msg_type,
                    msg.subject,
                    msg.body,
                    json.dumps(msg.payload),
                    msg.timestamp.isoformat(),
                ),
            )
            conn.commit()

    def list_messages(self, run_id: Optional[str] = None) -> List[OrchestrationMessage]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if run_id:
                cursor.execute("SELECT * FROM orchestration_messages WHERE run_id = ? ORDER BY timestamp ASC", (run_id,))
            else:
                cursor.execute("SELECT * FROM orchestration_messages ORDER BY timestamp ASC")
            messages = []
            for row in cursor.fetchall():
                d = dict(row)
                d["payload"] = json.loads(d.get("payload_json") or "{}")
                messages.append(OrchestrationMessage.from_dict(d))
            return messages
