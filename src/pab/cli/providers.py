"""Providers CLI commands."""

import json
from rich.console import Console
from rich.table import Table
import typer

from pab.providers.detector import ProviderRegistry

providers_app = typer.Typer(help="Manage and inspect agent platform providers")
console = Console()


@providers_app.command("list")
def list_providers(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all supported agent providers."""
    reg = ProviderRegistry()
    all_p = reg.detect_all()

    if as_json:
        console.print(json.dumps(all_p, indent=2))
        return

    table = Table(title="Supported Agent Providers")
    table.add_column("Key", style="cyan")
    table.add_column("Display Name", style="white")
    table.add_column("Status", style="green")
    table.add_column("Version", style="yellow")

    for k, v in all_p.items():
        status = "✅ Active" if v["detected"] else "⚠️ Inactive"
        table.add_row(k, v["display_name"], status, v["version"] or "—")

    console.print(table)


@providers_app.command("capabilities")
def show_capabilities(
    provider_name: str = typer.Argument(None, help="Optional provider key to filter"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show detailed capability matrix for providers."""
    reg = ProviderRegistry()
    all_p = reg.detect_all()

    if provider_name:
        all_p = {k: v for k, v in all_p.items() if k.lower() == provider_name.lower()}

    if as_json:
        console.print(json.dumps(all_p, indent=2))
        return

    for k, v in all_p.items():
        console.print(f"\n[bold cyan]{v['display_name']} ({k})[/bold cyan]")
        console.print(f"Status: {'Active' if v['detected'] else 'Not Detected'}")
        if v.get("capabilities"):
            for cap, val in v["capabilities"].items():
                console.print(f"  - [white]{cap}[/white]: [dim]{val}[/dim]")
        else:
            console.print("  [dim]No capabilities reported[/dim]")
