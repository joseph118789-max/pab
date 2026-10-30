"""Instruction and AGENTS.md CLI commands."""

from pathlib import Path
from rich.console import Console
import typer

from pab.instructions.manager import InstructionManager

instruction_app = typer.Typer(help="Manage canonical AGENTS.md and instruction files")
console = Console()


@instruction_app.command("show")
def show_instructions():
    """Display canonical AGENTS.md content."""
    im = InstructionManager()
    console.print(im.get_canonical())


@instruction_app.command("import")
def import_instructions(
    file_path: str = typer.Argument(..., help="Path to instruction file (e.g. CLAUDE.md or GEMINI.md)"),
    provider: str = typer.Option("generic", "--from", help="Source provider platform"),
):
    """Import and non-destructively merge external instructions into canonical AGENTS.md."""
    im = InstructionManager()
    p = Path(file_path)
    if not p.is_file():
        console.print(f"[red]Error: File '{file_path}' not found.[/red]")
        raise typer.Exit(1)

    merged = im.import_instructions(p, provider=provider)
    console.print(f"[green]Successfully merged instructions from {file_path} into canonical AGENTS.md[/green]")


@instruction_app.command("export")
def export_instructions(
    target_provider: str = typer.Option(..., "--to", help="Target provider (openclaw|agy|codex|claude)"),
    workspace_dir: str = typer.Option(".", "--dir", help="Target directory for generated instruction file"),
):
    """Export canonical instructions to provider-native instruction format."""
    im = InstructionManager()
    dest = im.export_for_provider(target_provider, Path(workspace_dir))
    console.print(f"[green]Exported {target_provider} instructions to:[/green] {dest}")


@instruction_app.command("compare")
def compare_instructions(
    file_a: str = typer.Argument(..., help="First instruction file"),
    file_b: str = typer.Argument(..., help="Second instruction file"),
):
    """Compare two instruction files and display differences and conflicts."""
    im = InstructionManager()
    res = im.compare_files(Path(file_a), Path(file_b))

    if res["is_identical"]:
        console.print("[green]The two instruction files are identical.[/green]")
        return

    console.print(f"[yellow]Unified Diff:[/yellow]\n{res['diff']}")
    if res["conflicting_sections"]:
        console.print("\n[red]Conflicting Sections:[/red]")
        for c in res["conflicting_sections"]:
            console.print(f"  - [bold]{c['section']}[/bold]")
