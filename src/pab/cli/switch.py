"""CLI commands for agent switching history, inspection, and rollback."""

import json
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
import typer
import yaml

from pab.core.config import ConfigManager
from pab.core.db import Database
from pab.switch.engine import SwitchEngine

switch_app = typer.Typer(help="One-command agent switching and session handoff history")
console = Console()


@switch_app.command("history")
def switch_history(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of records to show"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """View agent switching and session handoff history."""
    config = ConfigManager()
    db = Database(config.db_path)
    records = db.get_switch_history(limit=limit)

    if as_json:
        console.print(json.dumps(records, indent=2))
        return

    table = Table(title="Agent Switching & Session Handoff History")
    table.add_column("Handoff ID", style="cyan")
    table.add_column("From", style="yellow")
    table.add_column("To", style="green")
    table.add_column("Mode", style="magenta")
    table.add_column("Skills", style="white")
    table.add_column("Created At", style="blue")

    for r in records:
        skills = json.loads(r.get("skills_synced_json") or "[]")
        table.add_row(
            r["handoff_id"],
            r["source_provider"],
            r["target_provider"],
            r["mode"],
            str(len(skills)),
            r["created_at"][:19],
        )

    console.print(table)


@switch_app.command("inspect")
def inspect_handoff(
    handoff_id: str = typer.Argument(..., help="Handoff ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Inspect a handoff bundle, manifest, and context files."""
    config = ConfigManager()
    db = Database(config.db_path)
    record = db.get_switch_by_handoff(handoff_id)
    if not record:
        console.print(f"[red]Error: Switch record '{handoff_id}' not found in history.[/red]")
        raise typer.Exit(1)

    project_dir = Path(record["project_path"])
    handoff_dir = project_dir / ".pab" / "handoffs" / handoff_id
    manifest_file = handoff_dir / "manifest.json"

    if as_json:
        if manifest_file.is_file():
            console.print(manifest_file.read_text())
        else:
            console.print(json.dumps(record, indent=2))
        return

    console.print(f"\n[bold cyan]Handoff Bundle Inspection:[/bold cyan] [bold]{handoff_id}[/bold]")
    console.print(f"Source Provider: {record['source_provider']}")
    console.print(f"Destination Provider: {record['target_provider']}")
    console.print(f"Project Path: {record['project_path']}")
    console.print(f"Switch Mode: {record['mode']}")
    console.print(f"Created At: {record['created_at']}")

    if (handoff_dir / "HANDOFF.md").is_file():
        console.print("\n[bold green]--- HANDOFF.md Excerpt ---[/bold green]")
        lines = (handoff_dir / "HANDOFF.md").read_text(encoding="utf-8").splitlines()
        console.print("\n".join(lines[:25]))
        if len(lines) > 25:
            console.print(f"... ({len(lines) - 25} more lines)")


@switch_app.command("rollback")
def rollback_switch(
    handoff_id: str = typer.Argument(..., help="Handoff ID to roll back"),
):
    """Roll back a previous switch operation."""
    engine = SwitchEngine()
    try:
        ok = engine.rollback_switch(handoff_id)
        if ok:
            console.print(f"[green]Successfully rolled back switch handoff bundle:[/green] {handoff_id}")
        else:
            console.print(f"[yellow]Notice: Handoff directory for '{handoff_id}' was not found or already removed.[/yellow]")
    except Exception as e:
        console.print(f"[red]Rollback failed:[/red] {e}")
        raise typer.Exit(1)
