"""Universal Agent Orchestration CLI (pab run).

Standardizes multi-agent workflow coordination across OpenAI Codex, Anthropic Claude Code,
Google Antigravity (agy), OpenClaw, and Pi Coding Agent.
Implements Orca-inspired Runs, Tasks, Dispatches, Decision Gates, and Multi-Agent Results Aggregation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from pab.core.config import ConfigManager
from pab.core.models.orchestration import GateStatus, RunStatus, TaskStatus
from pab.core.orchestration_engine import OrchestrationEngine
from pab.providers.detector import ProviderRegistry
from pab.registry.agent_registry import AgentRegistry

run_app = typer.Typer(
    name="run",
    help="Universal multi-agent orchestration, execution dispatches, and decision gates",
    no_args_is_help=True,
)
gate_app = typer.Typer(help="Manage decision gates blocking orchestration tasks")
run_app.add_typer(gate_app, name="gate")

console = Console()


# -----------------------------------------------------------------------------
# Run Management Commands
# -----------------------------------------------------------------------------
@run_app.command("create")
def create_run_cmd(
    name: str = typer.Option(..., "--name", "-n", help="Human-readable run name"),
    objective: str = typer.Option(..., "--objective", "-o", help="Top-level objective for this run"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace root directory"),
    coordinator: Optional[str] = typer.Option(None, "--coordinator", "-c", help="Leading coordinator agent"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Create and bind a new lightweight orchestration Run."""
    engine = OrchestrationEngine()
    ws_path = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    run = engine.create_run(
        name=name,
        objective=objective,
        workspace_path=ws_path,
        coordinator_agent=coordinator,
    )

    if as_json:
        sys.stdout.write(json.dumps({"status": "ok", "run": run.to_dict()}, indent=2) + "\n")
        return

    console.print(f"[bold green]Orchestration Run Created:[/bold green] [cyan]{run.run_id}[/cyan]")
    console.print(f"Name: [bold]{run.name}[/bold]")
    console.print(f"Objective: {run.objective}")
    console.print(f"Workspace: {run.workspace_path}")
    if "orca_run_id" in run.metadata:
        console.print(f"Orca Bridge Bound: [green]{run.metadata['orca_run_id']}[/green]")


@run_app.command("list")
def list_runs_cmd(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status (active|completed|failed)"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """List active and historical orchestration runs."""
    engine = OrchestrationEngine()
    runs = engine.list_runs(status)

    if as_json:
        sys.stdout.write(json.dumps({"status": "ok", "runs": [r.to_dict() for r in runs]}, indent=2) + "\n")
        return

    if not runs:
        console.print("[yellow]No orchestration runs found.[/yellow]")
        return

    table = Table(title="PAB Orchestration Runs")
    table.add_column("Run ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Status")
    table.add_column("Objective")
    table.add_column("Created At")

    for r in runs:
        st_color = "green" if r.status == RunStatus.ACTIVE else "yellow" if r.status == RunStatus.COMPLETED else "red"
        table.add_row(
            r.run_id,
            r.name,
            f"[{st_color}]{r.status.value}[/{st_color}]",
            r.objective[:50] + ("..." if len(r.objective) > 50 else ""),
            r.created_at.strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)


# -----------------------------------------------------------------------------
# Task & Dispatch Commands
# -----------------------------------------------------------------------------
@run_app.command("task")
def create_task_cmd(
    run_id: str = typer.Option(..., "--run", "-r", help="Parent Run ID"),
    title: str = typer.Option(..., "--title", "-t", help="Concise task title"),
    spec: str = typer.Option(..., "--spec", help="Detailed task specification or prompt"),
    worker: Optional[str] = typer.Option(None, "--worker", "-w", help="Assigned PersonaOS worker ID"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Add a task to an active orchestration run."""
    engine = OrchestrationEngine()
    try:
        task = engine.create_task(run_id=run_id, title=title, spec=spec, worker_id=worker)
        if as_json:
            sys.stdout.write(json.dumps({"status": "ok", "task": task.to_dict()}, indent=2) + "\n")
            return
        console.print(f"[green]Task Created:[/green] [cyan]{task.task_id}[/cyan] in Run [bold]{run_id}[/bold]")
        console.print(f"Title: {task.title}")
    except Exception as exc:
        console.print(f"[red]Error creating task:[/red] {exc}")
        raise typer.Exit(1)


@run_app.command("dispatch")
def dispatch_task_cmd(
    agent: str = typer.Option(..., "--agent", "-a", help="Target agent provider (codex|claude|pi|agy|openclaw)"),
    task_id: Optional[str] = typer.Option(None, "--task", "-t", help="Existing task ID to dispatch"),
    spec: Optional[str] = typer.Option(None, "--spec", help="Task spec/prompt (creates task if --task omitted)"),
    run_id: Optional[str] = typer.Option(None, "--run", "-r", help="Run ID (defaults to latest active run)"),
    worker: Optional[str] = typer.Option(None, "--worker", "-w", help="PersonaOS persistent worker ID"),
    worktree: Optional[str] = typer.Option(None, "--worktree", help="Worktree or workspace directory path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate dispatch without starting processes"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Dispatch an agent execution attempt for a task."""
    engine = OrchestrationEngine()

    # Resolve Run ID if not specified
    target_run_id = run_id
    if not target_run_id:
        active_runs = engine.list_runs(status="active")
        if active_runs:
            target_run_id = active_runs[0].run_id
        else:
            # Auto-create run if neither is specified
            new_run = engine.create_run(
                name=f"dispatch-{agent}",
                objective=spec or f"Ad-hoc execution on {agent}",
                workspace_path=Path(worktree) if worktree else Path.cwd(),
            )
            target_run_id = new_run.run_id

    # Resolve Task ID
    target_task_id = task_id
    if not target_task_id:
        if not spec:
            console.print("[red]Error: Must provide either --task <id> or --spec <text>.[/red]")
            raise typer.Exit(1)
        t = engine.create_task(
            run_id=target_run_id,
            title=spec[:40],
            spec=spec,
            worker_id=worker,
        )
        target_task_id = t.task_id

    try:
        dispatch = engine.dispatch_task(
            run_id=target_run_id,
            task_id=target_task_id,
            agent_provider=agent,
            worker_id=worker,
            worktree_path=Path(worktree) if worktree else None,
            spec_override=spec,
            dry_run=dry_run,
        )

        if as_json:
            sys.stdout.write(json.dumps({"status": "ok", "dispatch": dispatch.to_dict()}, indent=2) + "\n")
            return

        console.print(f"[bold green]Dispatched Task '{target_task_id}' to {agent.upper()}:[/bold green]")
        console.print(f"Dispatch ID: [cyan]{dispatch.dispatch_id}[/cyan]")
        console.print(f"Worker: {dispatch.worker_id}")
        console.print(f"Status: [yellow]{dispatch.status.value}[/yellow]")
        console.print(f"Worktree: {dispatch.worktree_path}")
        if dispatch.process_id:
            console.print(f"Process PID: {dispatch.process_id}")
        if dispatch.result_summary:
            console.print(f"Result: {dispatch.result_summary}")

    except Exception as exc:
        console.print(f"[red]Dispatch Error:[/red] {exc}")
        raise typer.Exit(1)


@run_app.command("status")
def run_status_cmd(
    run_id: Optional[str] = typer.Option(None, "--run", "-r", help="Run ID to inspect"),
    dispatch_id: Optional[str] = typer.Option(None, "--dispatch", "-d", help="Dispatch ID to inspect"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Inspect orchestration run or dispatch state."""
    engine = OrchestrationEngine()

    if dispatch_id:
        disp = engine.db.get_dispatch(dispatch_id)
        if not disp:
            console.print(f"[red]Dispatch '{dispatch_id}' not found.[/red]")
            raise typer.Exit(1)
        if as_json:
            sys.stdout.write(json.dumps({"status": "ok", "dispatch": disp.to_dict()}, indent=2) + "\n")
            return
        console.print(f"[bold cyan]Dispatch {disp.dispatch_id}[/bold cyan]")
        console.print(f"Agent: {disp.agent_provider.upper()} | Worker: {disp.worker_id}")
        console.print(f"Status: {disp.status.value}")
        console.print(f"Started: {disp.started_at.isoformat()}")
        if disp.result_summary:
            console.print(f"Summary: {disp.result_summary}")
        return

    # Inspect Run
    target_run_id = run_id
    if not target_run_id:
        runs = engine.list_runs()
        if not runs:
            console.print("[yellow]No runs found.[/yellow]")
            return
        target_run_id = runs[0].run_id

    run = engine.get_run(target_run_id)
    if not run:
        console.print(f"[red]Run '{target_run_id}' not found.[/red]")
        raise typer.Exit(1)

    tasks = engine.list_tasks(target_run_id)
    dispatches = engine.db.list_dispatches(run_id=target_run_id)

    if as_json:
        payload = {
            "status": "ok",
            "run": run.to_dict(),
            "tasks": [t.to_dict() for t in tasks],
            "dispatches": [d.to_dict() for d in dispatches],
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return

    console.print(f"[bold cyan]Run: {run.name}[/bold cyan] (`{run.run_id}`) [{run.status.value.upper()}]")
    console.print(f"Objective: {run.objective}\n")

    if tasks:
        table = Table(title="Tasks")
        table.add_column("Task ID", style="cyan")
        table.add_column("Title")
        table.add_column("Status")
        table.add_column("Gate")
        for t in tasks:
            st_color = "green" if t.status == TaskStatus.COMPLETED else "red" if t.status == TaskStatus.BLOCKED else "yellow"
            table.add_row(t.task_id, t.title, f"[{st_color}]{t.status.value}[/{st_color}]", t.gate_id or "-")
        console.print(table)
        console.print()

    if dispatches:
        dtable = Table(title="Dispatches")
        dtable.add_column("Dispatch ID", style="cyan")
        dtable.add_column("Agent")
        dtable.add_column("Worker")
        dtable.add_column("Status")
        dtable.add_column("PID")
        for d in dispatches:
            dtable.add_row(d.dispatch_id, d.agent_provider, d.worker_id, d.status.value, str(d.process_id or "-"))
        console.print(dtable)


# -----------------------------------------------------------------------------
# Decision Gates
# -----------------------------------------------------------------------------
@gate_app.command("create")
def gate_create_cmd(
    task_id: str = typer.Option(..., "--task", "-t", help="Task ID to block"),
    question: str = typer.Option(..., "--question", "-q", help="Decision question for reviewer"),
    options: Optional[str] = typer.Option('["approve", "reject"]', "--options", help="JSON list of valid choices"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Create a decision gate blocking task execution until resolved."""
    engine = OrchestrationEngine()
    try:
        opt_list = json.loads(options) if options else ["approve", "reject"]
        gate = engine.create_decision_gate(task_id=task_id, question=question, options=opt_list)
        if as_json:
            sys.stdout.write(json.dumps({"status": "ok", "gate": gate.to_dict()}, indent=2) + "\n")
            return
        console.print(f"[bold yellow]Decision Gate Created:[/bold yellow] [cyan]{gate.gate_id}[/cyan]")
        console.print(f"Blocking Task: {task_id}")
        console.print(f"Question: [bold]{gate.question}[/bold]")
        console.print(f"Options: {', '.join(gate.options)}")
    except Exception as exc:
        console.print(f"[red]Error creating gate:[/red] {exc}")
        raise typer.Exit(1)


@gate_app.command("resolve")
def gate_resolve_cmd(
    gate_id: str = typer.Option(..., "--gate", "-g", help="Gate ID to resolve"),
    choice: str = typer.Option(..., "--choice", "-c", help="Selected decision option"),
    resolved_by: str = typer.Option("human", "--by", help="Identifier of decider (human or agent ID)"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Resolve an outstanding decision gate."""
    engine = OrchestrationEngine()
    try:
        gate = engine.resolve_decision_gate(gate_id=gate_id, choice=choice, resolved_by=resolved_by)
        if as_json:
            sys.stdout.write(json.dumps({"status": "ok", "gate": gate.to_dict()}, indent=2) + "\n")
            return
        console.print(f"[bold green]Gate {gate.gate_id} Resolved:[/bold green] [cyan]{gate.resolution}[/cyan]")
        console.print(f"Decider: {gate.resolved_by}")
        console.print(f"Task unblocked for execution.")
    except Exception as exc:
        console.print(f"[red]Error resolving gate:[/red] {exc}")
        raise typer.Exit(1)


@gate_app.command("list")
def gate_list_cmd(
    task_id: Optional[str] = typer.Option(None, "--task", "-t", help="Filter by task ID"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """List decision gates."""
    engine = OrchestrationEngine()
    gates = engine.db.list_decision_gates(task_id)
    if as_json:
        sys.stdout.write(json.dumps({"status": "ok", "gates": [g.to_dict() for g in gates]}, indent=2) + "\n")
        return
    if not gates:
        console.print("[yellow]No decision gates found.[/yellow]")
        return
    table = Table(title="Decision Gates")
    table.add_column("Gate ID", style="cyan")
    table.add_column("Task ID")
    table.add_column("Status")
    table.add_column("Question")
    table.add_column("Resolution")
    for g in gates:
        st_color = "yellow" if g.status == GateStatus.PENDING else "green"
        table.add_row(g.gate_id, g.task_id, f"[{st_color}]{g.status.value}[/{st_color}]", g.question, g.resolution or "-")
    console.print(table)


# -----------------------------------------------------------------------------
# Results Aggregation (Use Cases B & C)
# -----------------------------------------------------------------------------
@run_app.command("results")
def run_results_cmd(
    run_id: Optional[str] = typer.Option(None, "--run", "-r", help="Run ID to aggregate results for"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Synthesize multi-agent dispatch results into a single report."""
    engine = OrchestrationEngine()

    target_run_id = run_id
    if not target_run_id:
        runs = engine.list_runs()
        if not runs:
            console.print("[yellow]No runs found to aggregate.[/yellow]")
            return
        target_run_id = runs[0].run_id

    try:
        report = engine.get_run_results(target_run_id)
        if as_json:
            sys.stdout.write(json.dumps(report, indent=2) + "\n")
            return
        console.print(report["report_markdown"])
    except Exception as exc:
        console.print(f"[red]Error compiling run results:[/red] {exc}")
        raise typer.Exit(1)


# -----------------------------------------------------------------------------
# Inter-Agent Messaging
# -----------------------------------------------------------------------------
@run_app.command("send")
def send_msg_cmd(
    run_id: str = typer.Option(..., "--run", "-r", help="Run ID to scope message"),
    subject: str = typer.Option(..., "--subject", "-s", help="Message subject"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="Message body content"),
    msg_type: str = typer.Option("status", "--type", help="Message type (status|question|worker_done|heartbeat)"),
    to_target: Optional[str] = typer.Option(None, "--to", help="Target agent or worker"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """Send an inter-agent orchestration message."""
    engine = OrchestrationEngine()
    try:
        msg = engine.send_message(
            run_id=run_id,
            subject=subject,
            body=body,
            msg_type=msg_type,
            to_target=to_target,
        )
        if as_json:
            sys.stdout.write(json.dumps({"status": "ok", "message": msg.to_dict()}, indent=2) + "\n")
            return
        console.print(f"[green]Message Sent:[/green] {msg.subject} (ID: {msg.message_id})")
    except Exception as exc:
        console.print(f"[red]Error sending message:[/red] {exc}")
        raise typer.Exit(1)


@run_app.command("inbox")
def list_messages_cmd(
    run_id: Optional[str] = typer.Option(None, "--run", "-r", help="Run ID to view messages for"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output machine-readable JSON"),
):
    """View orchestration messages and worker reports."""
    engine = OrchestrationEngine()
    msgs = engine.list_messages(run_id)
    if as_json:
        sys.stdout.write(json.dumps({"status": "ok", "messages": [m.to_dict() for m in msgs]}, indent=2) + "\n")
        return
    if not msgs:
        console.print("[yellow]Inbox empty.[/yellow]")
        return
    for m in msgs:
        console.print(f"• [bold cyan]#{m.message_id}[/bold cyan] [[yellow]{m.msg_type}[/yellow]] @ {m.timestamp.strftime('%H:%M:%S')}")
        console.print(f"  Subject: [bold]{m.subject}[/bold] (From: {m.from_handle} ➔ To: {m.to_target or 'all'})")
        if m.body:
            console.print(f"  {m.body}")
        console.print()


# -----------------------------------------------------------------------------
# Backward Compatibility: pab run agent <id>
# -----------------------------------------------------------------------------
def execute_run(
    agent_id: str,
    provider_name: str = "openclaw",
    handoff_session: Optional[str] = None,
):
    """Launch an agent through the specified provider platform."""
    config = ConfigManager()
    reg = AgentRegistry(config)
    providers = ProviderRegistry(workspace_root=config.root.parent)

    provider = providers.get(provider_name.lower())
    if not provider:
        console.print(f"[red]Error: Provider '{provider_name}' not supported.[/red]")
        raise typer.Exit(1)

    if not provider.detect():
        console.print(f"[red]Error: Provider '{provider.display_name}' is not installed or available on this system.[/red]")
        raise typer.Exit(1)

    agent_profile = reg.get_agent(agent_id)
    if not agent_profile:
        console.print(f"[red]Error: Agent '{agent_id}' does not exist in PAB registry.[/red]")
        raise typer.Exit(1)

    existing = provider.get_agent(agent_id)
    if not existing:
        console.print(f"[yellow]Agent '{agent_id}' not yet deployed to {provider.display_name}. Auto-deploying...[/yellow]")
        provider.create_agent(agent_profile.agent)

    if handoff_session:
        from pab.sessions.manager import SessionMigrationManager
        sm = SessionMigrationManager(config)
        sm.import_context(provider_name, handoff_session)
        console.print(f"[green]Injected portable handoff context from session {handoff_session}[/green]")

    console.print(f"[bold green]Ready to launch '{agent_profile.agent.name}' on {provider.display_name}![/bold green]")
    console.print(f"Platform: {provider.display_name} (Version: {provider.version() or 'Detected'})")
    console.print(f"Agent: {agent_profile.agent.name} (Role: {agent_profile.agent.identity.role})")


@run_app.command("agent")
def run_agent_cmd(
    agent_id: str = typer.Argument(..., help="Agent ID to run"),
    provider_name: str = typer.Option("openclaw", "--provider", "-p", help="Target provider (openclaw|agy|codex|claude|pi)"),
    handoff_session: Optional[str] = typer.Option(None, "--with-handoff", help="Optional session ID to inject handoff context before launch"),
):
    """Legacy runner: launch an agent through provider."""
    execute_run(agent_id, provider_name, handoff_session)
