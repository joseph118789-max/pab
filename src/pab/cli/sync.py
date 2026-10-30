"""Synchronisation and Reconciliation CLI commands."""

import json
from rich.console import Console
from rich.table import Table
import typer

from pab.sync.engine import SyncEngine

sync_app = typer.Typer(help="Synchronisation and reconciliation engine")
console = Console()


@sync_app.command("plan")
def plan_sync(
    targets: str = typer.Option("all", "--to", help="Target providers (comma-separated or 'all')"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Generate a non-destructive synchronisation change plan."""
    engine = SyncEngine()
    target_list = [t.strip() for t in targets.split(",")]
    plan = engine.plan(target_list)

    if as_json:
        console.print(json.dumps(plan.model_dump(), indent=2))
        return

    console.print(f"\n[bold]Reconciliation Plan:[/bold] [cyan]{plan.plan_id}[/cyan]")
    console.print(f"Targets: {', '.join(plan.targets)}")

    table = Table(title="Proposed Operations")
    table.add_column("Type", style="cyan")
    table.add_column("Resource", style="white")
    table.add_column("Provider", style="magenta")
    table.add_column("Action", style="green")
    table.add_column("Description", style="dim")

    for op in plan.operations:
        table.add_row(
            op.resource_type,
            op.resource_id,
            op.target_provider,
            op.action.upper(),
            op.description,
        )

    console.print(table)
    console.print(f"\nRun [bold green]pab sync apply {plan.plan_id}[/bold green] to apply this plan.")


@sync_app.command("apply")
def apply_plan(
    plan_id: str = typer.Argument(..., help="Plan ID to execute"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Apply an approved synchronisation plan atomically with pre-backup."""
    engine = SyncEngine()
    try:
        results = engine.apply(plan_id)
        if as_json:
            console.print(json.dumps(results, indent=2))
            return

        console.print(f"[green]Successfully applied synchronisation plan '{plan_id}'![/green]")
        console.print(f"Applied operations: {results['applied_operations']}")
        if results.get("failed_operations", 0) > 0:
            console.print(f"[yellow]Failed operations: {results['failed_operations']}[/yellow]")
            for err in results.get("errors", []):
                console.print(f"  - ❌ {err}")
    except Exception as e:
        console.print(f"[red]Plan execution failed:[/red] {e}")
        raise typer.Exit(1)
