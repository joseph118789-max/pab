"""PAB Control Plane machine-readable CLI commands.

Provides stable, versioned JSON interface for PersonaOS and external orchestrators:
`pab control list-agents --json`
`pab control launch ... --json`
`pab control status <id> --json`
`pab control stop <id> --json`
`pab control events <id> --json`
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from pab.core.capability_registry import CapabilityRegistry
from pab.core.config import ConfigManager
from pab.core.execution_supervisor import ExecutionSupervisor
from pab.core.models.execution import ExecutionMode, LaunchRequest

control_app = typer.Typer(
    help="Machine-readable Agent Control Plane operations",
    no_args_is_help=True,
)
console = Console()


def _output_json_or_text(payload: dict, as_json: bool, text_render_fn=None):
    if as_json:
        # Machine-readable output to stdout
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        sys.stdout.flush()
    else:
        if text_render_fn:
            text_render_fn()
        else:
            console.print(payload)


@control_app.command("list-agents")
def list_agents(
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Enumerate available agent runtimes, detected versions, and verified capabilities."""
    registry = CapabilityRegistry()
    caps = registry.list_capabilities()

    payload = {
        "contract_version": "1.0",
        "status": "ok",
        "agents": [c.to_dict() for c in caps],
    }

    def render_text():
        console.print("[bold cyan]PAB Control Plane — Detected Agent Runtimes[/bold cyan]\n")
        for c in caps:
            st = "[green]Ready[/green]" if c.available else "[red]Offline[/red]"
            v = f"v{c.detected_version}" if c.detected_version else "N/A"
            console.print(f"• [bold]{c.display_name}[/bold] ({c.provider}): {st} | Version: {v}")
            console.print(f"  Operations: {', '.join(c.supported_operations)}")
            console.print(f"  Modes: {', '.join(c.supported_execution_modes)}")
            if c.detection_errors:
                for err in c.detection_errors:
                    console.print(f"  [yellow]Warning:[/yellow] {err}")
            console.print()

    _output_json_or_text(payload, as_json, render_text)


@control_app.command("launch")
def launch_execution(
    provider: str = typer.Option(..., "--provider", "-p", help="Target provider runtime"),
    worker_id: str = typer.Option(..., "--worker", "-w", help="PersonaOS persistent worker ID"),
    task_id: str = typer.Option(..., "--task", "-t", help="PersonaOS task ID"),
    workspace: str = typer.Option(".", "--workspace", help="Target workspace path"),
    idempotency_key: Optional[str] = typer.Option(None, "--idempotency-key", "-k", help="Idempotency key"),
    request_id: Optional[str] = typer.Option(None, "--request-id", help="Correlation request ID"),
    generation: int = typer.Option(1, "--generation", "-g", help="Execution generation fence"),
    mode: str = typer.Option("managed_process", "--mode", "-m", help="Execution mode: managed_process | orca_terminal"),
    command: Optional[str] = typer.Option(None, "--command", "-c", help="Custom command to run"),
    prompt: Optional[str] = typer.Option(None, "--prompt", help="Prompt to execute"),
    timeout: float = typer.Option(300.0, "--timeout", help="Timeout in seconds"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Launch an external agent execution with idempotency guard."""
    supervisor = ExecutionSupervisor()
    req_id = request_id or f"req-{uuid.uuid4().hex[:12]}"
    idem_key = idempotency_key or req_id
    exec_mode = ExecutionMode(mode) if mode in [m.value for m in ExecutionMode] else ExecutionMode.MANAGED_PROCESS

    req = LaunchRequest(
        request_id=req_id,
        idempotency_key=idem_key,
        worker_id=worker_id,
        task_id=task_id,
        provider=provider,
        workspace_path=Path(workspace).resolve(),
        execution_generation=generation,
        execution_mode=exec_mode,
        timeout_seconds=timeout,
        command=command,
        prompt=prompt,
    )

    try:
        handle = supervisor.launch(req)
        payload = {
            "contract_version": "1.0",
            "status": "ok",
            "execution": handle.to_dict(),
        }

        def render_text():
            console.print(f"[green]Execution Launched Successfully[/green]")
            console.print(f"Execution ID: [bold]{handle.execution_id}[/bold]")
            console.print(f"Status: {handle.status.value}")
            console.print(f"Provider: {handle.provider} ({handle.execution_mode.value})")
            if handle.process_id:
                console.print(f"PID: {handle.process_id}")
            if handle.terminal_handle:
                console.print(f"Terminal: {handle.terminal_handle}")

        _output_json_or_text(payload, as_json, render_text)
    except Exception as exc:
        err_payload = {
            "contract_version": "1.0",
            "status": "error",
            "error_type": exc.__class__.__name__,
            "message": str(exc),
        }
        if as_json:
            sys.stdout.write(json.dumps(err_payload, indent=2) + "\n")
            raise typer.Exit(1)
        else:
            console.print(f"[red]Launch Error:[/red] {exc}")
            raise typer.Exit(1)


@control_app.command("status")
def execution_status(
    execution_id: str = typer.Argument(..., help="PAB execution ID to query"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Inspect live status and process state for an execution."""
    supervisor = ExecutionSupervisor()
    try:
        handle = supervisor.get_execution(execution_id)
        payload = {
            "contract_version": "1.0",
            "status": "ok",
            "execution": handle.to_dict(),
        }

        def render_text():
            console.print(f"Execution: [bold]{handle.execution_id}[/bold]")
            console.print(f"Worker: {handle.worker_id} | Task: {handle.task_id}")
            console.print(f"Status: [cyan]{handle.status.value}[/cyan]")
            if handle.exit_code is not None:
                console.print(f"Exit Code: {handle.exit_code}")
            if handle.error_message:
                console.print(f"Error: [red]{handle.error_message}[/red]")

        _output_json_or_text(payload, as_json, render_text)
    except Exception as exc:
        err_payload = {
            "contract_version": "1.0",
            "status": "error",
            "error_type": exc.__class__.__name__,
            "message": str(exc),
        }
        if as_json:
            sys.stdout.write(json.dumps(err_payload, indent=2) + "\n")
            raise typer.Exit(1)
        else:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)


@control_app.command("stop")
def stop_execution(
    execution_id: str = typer.Argument(..., help="PAB execution ID to terminate"),
    force: bool = typer.Option(False, "--force", "-f", help="Force SIGKILL"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Terminate an active agent execution."""
    supervisor = ExecutionSupervisor()
    try:
        handle = supervisor.stop(execution_id, force=force)
        payload = {
            "contract_version": "1.0",
            "status": "ok",
            "execution": handle.to_dict(),
        }

        def render_text():
            console.print(f"[yellow]Execution Cancelled:[/yellow] {handle.execution_id}")
            console.print(f"Final Status: {handle.status.value}")

        _output_json_or_text(payload, as_json, render_text)
    except Exception as exc:
        err_payload = {
            "contract_version": "1.0",
            "status": "error",
            "error_type": exc.__class__.__name__,
            "message": str(exc),
        }
        if as_json:
            sys.stdout.write(json.dumps(err_payload, indent=2) + "\n")
            raise typer.Exit(1)
        else:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)


@control_app.command("events")
def list_events(
    execution_id: str = typer.Argument(..., help="PAB execution ID"),
    since: int = typer.Option(0, "--since", "-s", help="Sequence number offset"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Retrieve sequenced execution events for an execution."""
    supervisor = ExecutionSupervisor()
    events = supervisor.list_events(execution_id, since_sequence=since)
    payload = {
        "contract_version": "1.0",
        "status": "ok",
        "execution_id": execution_id,
        "events": [e.to_dict() for e in events],
    }

    def render_text():
        console.print(f"Events for Execution [bold]{execution_id}[/bold] (Since seq {since}):\n")
        for e in events:
            console.print(f"#{e.sequence_number} [{e.event_type}] @ {e.timestamp.isoformat()}")
            if e.payload:
                console.print(f"   Payload: {e.payload}")

    _output_json_or_text(payload, as_json, render_text)


@control_app.command("handoff")
def handoff_execution(
    source: str = typer.Option(..., "--source", "-s", help="Source agent provider"),
    target: str = typer.Option(..., "--target", "-t", help="Target agent provider"),
    worker: Optional[str] = typer.Option(None, "--worker", "-w", help="PersonaOS worker ID"),
    session_id: Optional[str] = typer.Option(None, "--session-id", help="Native source session ID"),
    execution_id: Optional[str] = typer.Option(None, "--execution-id", "-e", help="Prior execution ID to hand off"),
    project: Path = typer.Option(Path.cwd(), "--project", "-p", help="Target project workspace"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate handoff bundle generation without launching"),
    launch: bool = typer.Option(False, "--launch", help="Launch target agent after handoff bundle generation"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Orchestrate cross-provider context handoff and session transfer."""
    from pab.switch.engine import SwitchEngine
    from pab.switch.models import SwitchMode
    supervisor = ExecutionSupervisor()

    if execution_id:
        try:
            handle = supervisor.get_execution(execution_id)
            if not session_id and handle.native_session_id:
                session_id = handle.native_session_id
            if not worker and handle.worker_id:
                worker = handle.worker_id
            if not source and handle.provider:
                source = handle.provider
        except Exception:
            pass

    engine = SwitchEngine()
    try:
        plan = engine.plan_switch(
            target_provider_name=target,
            source_provider_name=source,
            session_id=session_id,
            agent_id=worker,
            project_path=project,
            mode=SwitchMode.HANDOFF,
        )

        res = engine.execute_switch(plan, dry_run=dry_run)

        handoff_data = {
            "handoff_id": res.handoff_id,
            "source_provider": plan.source_provider,
            "destination_provider": plan.destination_provider,
            "worker_id": worker,
            "session_id": session_id,
            "project_path": str(project),
            "handoff_dir": res.handoff_dir,
            "skills_synced": res.manifest.imported_skills,
            "warnings": res.warnings,
            "dry_run": dry_run,
            "launched": res.launched,
        }

        payload = {
            "contract_version": "1.0",
            "status": "ok",
            "handoff": handoff_data,
        }

        def render_text():
            console.print(f"[bold green]Handoff {'(Dry Run) ' if dry_run else ''}Created:[/bold green] {res.handoff_id}")
            console.print(f"Source: {plan.source_provider} ➔ Destination: {plan.destination_provider}")
            console.print(f"Handoff Directory: {res.handoff_dir}")
            if res.manifest.imported_skills:
                console.print(f"Skills synced: {', '.join(res.manifest.imported_skills)}")
            if res.warnings:
                for w in res.warnings:
                    console.print(f"[yellow]Warning:[/yellow] {w}")

        _output_json_or_text(payload, as_json, render_text)
    except Exception as exc:
        err_payload = {
            "contract_version": "1.0",
            "status": "error",
            "error_type": exc.__class__.__name__,
            "message": str(exc),
        }
        if as_json:
            sys.stdout.write(json.dumps(err_payload, indent=2) + "\n")
            raise typer.Exit(1)
        else:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

