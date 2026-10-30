"""Memory Hub CLI commands."""

import json
from rich.console import Console
from rich.table import Table
import typer

from pab.memory.hub import MemoryHub

memory_app = typer.Typer(help="Unified Multi-Tier Memory Hub")
console = Console()


@memory_app.command("list")
def list_memories(
    scope: str = typer.Option(None, "--scope", "-s", help="Filter by scope (user|global|project|agent|daily|imported|handoff)"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List memory items stored in the Memory Hub."""
    hub = MemoryHub()
    items = hub.list_memories(scope=scope)

    if as_json:
        console.print(json.dumps([m.model_dump() for m in items], indent=2))
        return

    table = Table(title="PAB Memory Hub")
    table.add_column("Memory ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Scope", style="yellow")
    table.add_column("Source", style="magenta")
    table.add_column("Status", style="green")

    for m in items:
        status = "⚠️ Untrusted" if m.untrusted else "✅ Verified"
        table.add_row(
            m.id[:20],
            m.title[:40],
            m.scope,
            m.source_provider or "PAB",
            status,
        )

    console.print(table)


@memory_app.command("search")
def search_memories(
    query: str = typer.Argument(..., help="Search query"),
    scope: str = typer.Option(None, "--scope", "-s", help="Optional scope filter"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Search stored memories by keyword."""
    hub = MemoryHub()
    matches = hub.search(query, scope=scope)

    if as_json:
        console.print(json.dumps([m.model_dump() for m in matches], indent=2))
        return

    console.print(f"\n[bold]Found {len(matches)} memory match(es) for '{query}':[/bold]\n")
    for m in matches:
        console.print(f"[bold cyan]{m.title}[/bold cyan] ({m.scope} / {m.source_provider or 'PAB'})")
        console.print(f"[dim]{m.content[:200]}...[/dim]\n")


@memory_app.command("import")
def import_provider_memory(
    provider_name: str = typer.Argument(..., help="Source provider (openclaw|codex|claude|agy)"),
):
    """Import memories from a native provider into the Memory Hub (tagged untrusted for safety)."""
    hub = MemoryHub()
    res = hub.import_from_provider(provider_name.lower())
    console.print(f"[green]Memory Import Complete for {provider_name}:[/green]")
    console.print(f"  - Found: {res['total_found']}")
    console.print(f"  - Added: {res['added']}")
    console.print(f"  - Skipped Duplicates: {res['skipped_duplicates']}")


@memory_app.command("backup")
def backup_memories():
    """Create a point-in-time snapshot backup of all memory files."""
    hub = MemoryHub()
    dest = hub.backup_memories()
    console.print(f"[green]Created memory backup at:[/green] {dest}")
