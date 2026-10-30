"""Session Migration CLI commands."""

import json
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
import typer

from pab.sessions.manager import SessionMigrationManager

session_app = typer.Typer(help="Cross-platform session discovery, export, and handoff")
console = Console()


@session_app.command("list")
def list_sessions(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Filter by provider"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List sessions discovered across providers."""
    sm = SessionMigrationManager()
    sessions = sm.list_sessions(provider_name=provider)

    if as_json:
        console.print(json.dumps(sessions, indent=2))
        return

    table = Table(title="Discovered Native Agent Sessions")
    table.add_column("Session ID", style="cyan")
    table.add_column("Provider", style="magenta")
    table.add_column("Details", style="white")

    for s in sessions:
        details = s.get("session_file") or s.get("transcript_path") or s.get("created_at") or "active"
        table.add_row(str(s["id"]), s.get("provider", "unknown"), str(details))

    console.print(table)


@session_app.command("export")
def export_session(
    provider: str = typer.Option(..., "--provider", "-p", help="Source provider"),
    session_id: str = typer.Option(..., "--session", "-s", help="Session ID to export"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Export and normalize a native provider session."""
    sm = SessionMigrationManager()
    try:
        norm = sm.export_session(provider, session_id)
        if as_json:
            console.print(json.dumps(norm.model_dump(), indent=2))
            return
        console.print(f"[green]Successfully exported session '{session_id}' from {provider}![/green]")
        console.print(f"Normalized ID: [cyan]{norm.id}[/cyan]")
        console.print(f"Objective: {norm.context.original_objective or 'N/A'}")
        console.print(f"Summary: {norm.context.task_summary}")
    except Exception as e:
        console.print(f"[red]Export failed:[/red] {e}")
        raise typer.Exit(1)


@session_app.command("handoff")
def create_handoff(
    from_provider: str = typer.Option(..., "--from", help="Source provider"),
    to_provider: Optional[str] = typer.Option(None, "--to", help="Target provider"),
    session_id: str = typer.Option(..., "--session", "-s", help="Session ID"),
):
    """Build a Portable Handoff Package (HANDOFF.md + context.json)."""
    sm = SessionMigrationManager()
    try:
        bundle = sm.create_handoff(from_provider, to_provider, session_id)
        console.print(f"[green]Successfully generated Portable Handoff Bundle:[/green] [bold]{bundle.bundle_id}[/bold]")
        console.print(f"Source: [cyan]{bundle.source_provider}[/cyan] -> Target: [magenta]{bundle.target_provider or 'Any'}[/magenta]")
    except Exception as e:
        console.print(f"[red]Handoff creation failed:[/red] {e}")
        raise typer.Exit(1)


@session_app.command("import-context")
def import_context(
    provider: str = typer.Option(..., "--provider", "-p", help="Target provider"),
    session_id: str = typer.Option(..., "--session", "-s", help="Session ID"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Target workspace path"),
):
    """Inject a portable handoff package context into the target provider's workspace."""
    sm = SessionMigrationManager()
    ws_path = Path(workspace) if workspace else None
    try:
        handoff_file = sm.import_context(provider, session_id, target_workspace=ws_path)
        console.print(f"[green]Injected handoff context for {provider} into:[/green] {handoff_file}")
    except Exception as e:
        console.print(f"[red]Context import failed:[/red] {e}")
        raise typer.Exit(1)


@session_app.command("resume")
def resume_session(
    provider: str = typer.Option(..., "--provider", "-p", help="Target provider"),
    session_id: str = typer.Option(..., "--session", "-s", help="Session ID"),
):
    """Resume session natively if supported on this provider."""
    sm = SessionMigrationManager()
    try:
        sm.resume_session(provider, session_id)
        console.print(f"[green]Session '{session_id}' resumed on {provider}.[/green]")
    except Exception as e:
        console.print(f"[red]Resume failed:[/red] {e}")
        raise typer.Exit(1)
