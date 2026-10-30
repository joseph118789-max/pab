"""PersonaOS Agent Bridge (PAB) CLI root."""

from pathlib import Path
from typing import Optional
from rich.console import Console
import typer

from pab import __version__
from pab.cli.agent import agent_app
from pab.cli.backup import backup_app
from pab.cli.doctor import doctor_app
from pab.cli.instruction import instruction_app
from pab.cli.memory import memory_app
from pab.cli.providers import providers_app
from pab.cli.run import run_app
from pab.cli.session import session_app
from pab.cli.skill import skill_app
from pab.cli.sync import sync_app
from pab.personaos.bridge import PersonaOSBridge

app = typer.Typer(
    name="pab",
    help="PersonaOS Agent Bridge (PAB): Universal AI Agent Manager across OpenClaw, Antigravity, Codex, and Claude Code.",
    no_args_is_help=True,
)
console = Console()

app.add_typer(doctor_app, name="doctor")
app.add_typer(providers_app, name="providers")
app.add_typer(agent_app, name="agent")
app.add_typer(skill_app, name="skill")
app.add_typer(instruction_app, name="instruction")
app.add_typer(memory_app, name="memory")
app.add_typer(session_app, name="session")
app.add_typer(sync_app, name="sync")
app.add_typer(backup_app, name="backup")


@app.command("run")
def run_cli_command(
    agent_id: str = typer.Argument(..., help="Agent ID to run"),
    provider: str = typer.Option("openclaw", "--provider", "-p", help="Target provider (openclaw|agy|codex|claude)"),
    with_handoff: Optional[str] = typer.Option(None, "--with-handoff", help="Optional session ID to inject handoff context before launch"),
):
    """Launch an agent through the specified provider platform."""
    from pab.cli.run import execute_run
    execute_run(agent_id, provider, with_handoff)

personaos_app = typer.Typer(help="PersonaOS worker profile integration")


@personaos_app.command("import")
def import_worker(
    profile_path: str = typer.Argument(..., help="Path to PersonaOS v1.yaml profile"),
):
    """Import a PersonaOS worker profile into canonical PAB agent registry."""
    bridge = PersonaOSBridge()
    p = Path(profile_path)
    if not p.is_file():
        console.print(f"[red]Error: Profile file '{profile_path}' not found.[/red]")
        raise typer.Exit(1)
    profile = bridge.import_worker_profile(p)
    console.print(f"[green]Successfully imported PersonaOS worker:[/green] [bold]{profile.agent.name}[/bold] ({profile.agent.id})")


@personaos_app.command("sync")
def sync_workers(
    profiles_dir: str = typer.Option("/root/projects/PersonaOS/profiles", "--dir", "-d", help="PersonaOS profiles directory"),
    targets: str = typer.Option("all", "--to", help="Target providers"),
):
    """Scan PersonaOS profiles directory and deploy workers & skills across providers."""
    bridge = PersonaOSBridge()
    p_dir = Path(profiles_dir)
    if not p_dir.is_dir():
        console.print(f"[red]Error: Profiles directory '{profiles_dir}' not found.[/red]")
        raise typer.Exit(1)

    target_list = [t.strip() for t in targets.split(",")]
    res = bridge.sync_worker_profiles(p_dir, target_providers=target_list)
    console.print(f"[green]PersonaOS Sync Complete:[/green] Imported {len(res['imported'])} workers: {', '.join(res['imported'])}")


@personaos_app.command("readiness")
def readiness_report():
    """Display provider readiness report for PersonaOS orchestrator."""
    bridge = PersonaOSBridge()
    report = bridge.get_readiness_report()
    console.print("[bold cyan]PersonaOS Provider Readiness Report:[/bold cyan]")
    for p_name, data in report["providers"].items():
        st = "✅ Ready" if data["detected"] else "❌ Offline"
        console.print(f"  - {data['display_name']} ({p_name}): {st} (Version: {data['version'] or 'N/A'})")
    console.print(f"Registered Canonical Agents: {report['registered_agents']}")


app.add_typer(personaos_app, name="personaos")


@app.callback()
def main_banner(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show PAB version and exit",
        is_eager=True,
    ),
):
    if version:
        console.print(f"[bold cyan]PersonaOS Agent Bridge (PAB)[/bold cyan] version [yellow]{__version__}[/yellow]")
        raise typer.Exit()


if __name__ == "__main__":
    app()
