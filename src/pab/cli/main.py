"""PersonaOS Agent Bridge (PAB) CLI root."""

import sys
from pathlib import Path
from typing import List, Optional
from rich.console import Console
import typer

from pab import __version__
from pab.cli.agent import agent_app
from pab.cli.backup import backup_app
from pab.cli.control import control_app
from pab.cli.doctor import doctor_app
from pab.cli.instruction import instruction_app
from pab.cli.memory import memory_app
from pab.cli.providers import providers_app
from pab.cli.run import run_app
from pab.cli.session import session_app
from pab.cli.skill import skill_app
from pab.cli.switch import switch_app
from pab.cli.sync import sync_app
from pab.personaos.bridge import PersonaOSBridge
from pab.switch.engine import SwitchEngine
from pab.switch.models import SwitchMode

app = typer.Typer(
    name="pab",
    help="PersonaOS Agent Bridge (PAB): Universal AI Agent Manager across OpenClaw, Antigravity, Codex, and Claude Code.",
    no_args_is_help=True,
)
console = Console()

# Register sub-command modules
app.add_typer(doctor_app, name="doctor")
app.add_typer(providers_app, name="providers")
app.add_typer(agent_app, name="agent")
app.add_typer(skill_app, name="skill")
app.add_typer(instruction_app, name="instruction")
app.add_typer(memory_app, name="memory")
app.add_typer(session_app, name="session")
app.add_typer(sync_app, name="sync")
app.add_typer(backup_app, name="backup")
app.add_typer(switch_app, name="switch")
app.add_typer(control_app, name="control")
app.add_typer(run_app, name="run")


def _execute_provider_switch(
    target_provider: str,
    from_provider: Optional[str] = None,
    session: Optional[str] = None,
    agent: Optional[str] = None,
    project: Optional[str] = None,
    mode: str = "handoff",
    no_skills: bool = False,
    no_memory: bool = False,
    dry_run: bool = False,
    extra_args: Optional[List[str]] = None,
):
    """Core executor for one-command agent switching and native launching."""
    engine = SwitchEngine()
    passed_extra = [a for a in (extra_args or []) if a != "--"]

    parsed_mode = SwitchMode(mode) if mode in [m.value for m in SwitchMode] else SwitchMode.HANDOFF

    plan = engine.plan_switch(
        target_provider_name=target_provider,
        source_provider_name=from_provider,
        session_id=session,
        agent_id=agent,
        project_path=Path(project) if project else None,
        mode=parsed_mode,
        no_skills=no_skills,
        no_memory=no_memory,
        extra_args=passed_extra,
    )

    if from_provider or dry_run:
        console.print(f"\n[bold cyan]Switching from {from_provider or 'none'} ➔ {target_provider}[/bold cyan]")
        console.print(f"Mode: [yellow]{plan.mode.value}[/yellow]")
        console.print(f"Project: {plan.project_path}")
        if plan.session_id:
            console.print(f"Source Session: {plan.session_id}")
        if plan.agent_id:
            console.print(f"Source Agent: {plan.agent_id}")
        if plan.skills_to_sync:
            console.print(f"Skills to Sync ({len(plan.skills_to_sync)}): {', '.join(plan.skills_to_sync)}")
        if plan.conflicting_skills:
            console.print("[yellow]Conflicting Skills detected:[/yellow]")
            for c in plan.conflicting_skills:
                console.print(f"  - {c['name']} (Source: {c['source_version']} vs Dest: {c['destination_version']})")
        for w in plan.warnings:
            console.print(f"  ⚠️  [yellow]{w}[/yellow]")

    if dry_run:
        console.print("\n[bold green]Dry-run complete.[/bold green] Target launch command would be:")
        console.print(f"  [cyan]{' '.join(plan.target_launch_cmd)}[/cyan]\n")
        return

    result = engine.execute_switch(plan, dry_run=dry_run, extra_args=passed_extra)
    if result.success and from_provider:
        console.print(f"\n[green]Handoff Bundle Generated:[/green] {result.handoff_id}")
        console.print(f"Bundle directory: {result.handoff_dir}")
        if result.launched:
            console.print(f"[green]Launched {target_provider} CLI successfully.[/green]")


# One-command switching top-level provider entrypoints
@app.command("codex", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def switch_to_codex(
    ctx: typer.Context,
    from_provider: Optional[str] = typer.Option(None, "--from", "-f", help="Source agent/provider platform"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID or 'latest'"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent ID"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project path"),
    mode: str = typer.Option("handoff", "--mode", "-m", help="Switch mode: handoff|clone|skills-only"),
    no_skills: bool = typer.Option(False, "--no-skills", help="Do not transfer skills"),
    no_memory: bool = typer.Option(False, "--no-memory", help="Do not transfer memory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Display migration plan without launching native CLI"),
):
    """Switch to OpenAI Codex CLI from another provider, or launch Codex directly."""
    _execute_provider_switch("codex", from_provider, session, agent, project, mode, no_skills, no_memory, dry_run, extra_args=ctx.args)


@app.command("claude", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def switch_to_claude(
    ctx: typer.Context,
    from_provider: Optional[str] = typer.Option(None, "--from", "-f", help="Source agent/provider platform"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID or 'latest'"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent ID"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project path"),
    mode: str = typer.Option("handoff", "--mode", "-m", help="Switch mode: handoff|clone|skills-only"),
    no_skills: bool = typer.Option(False, "--no-skills", help="Do not transfer skills"),
    no_memory: bool = typer.Option(False, "--no-memory", help="Do not transfer memory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Display migration plan without launching native CLI"),
):
    """Switch to Anthropic Claude Code from another provider, or launch Claude directly."""
    _execute_provider_switch("claude", from_provider, session, agent, project, mode, no_skills, no_memory, dry_run, extra_args=ctx.args)


@app.command("agy", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def switch_to_agy(
    ctx: typer.Context,
    from_provider: Optional[str] = typer.Option(None, "--from", "-f", help="Source agent/provider platform"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID or 'latest'"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent ID"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project path"),
    mode: str = typer.Option("handoff", "--mode", "-m", help="Switch mode: handoff|clone|skills-only"),
    no_skills: bool = typer.Option(False, "--no-skills", help="Do not transfer skills"),
    no_memory: bool = typer.Option(False, "--no-memory", help="Do not transfer memory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Display migration plan without launching native CLI"),
):
    """Switch to Google Antigravity CLI (agy) from another provider, or launch agy directly."""
    _execute_provider_switch("agy", from_provider, session, agent, project, mode, no_skills, no_memory, dry_run, extra_args=ctx.args)


@app.command("openclaw", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def switch_to_openclaw(
    ctx: typer.Context,
    from_provider: Optional[str] = typer.Option(None, "--from", "-f", help="Source agent/provider platform"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID or 'latest'"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent ID"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project path"),
    mode: str = typer.Option("handoff", "--mode", "-m", help="Switch mode: handoff|clone|skills-only"),
    no_skills: bool = typer.Option(False, "--no-skills", help="Do not transfer skills"),
    no_memory: bool = typer.Option(False, "--no-memory", help="Do not transfer memory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Display migration plan without launching native CLI"),
):
    """Switch to OpenClaw from another provider, or launch OpenClaw directly."""
    _execute_provider_switch("openclaw", from_provider, session, agent, project, mode, no_skills, no_memory, dry_run, extra_args=ctx.args)


@app.command("minimax", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def switch_to_minimax(
    ctx: typer.Context,
    from_provider: Optional[str] = typer.Option(None, "--from", "-f", help="Source agent/provider platform"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID or 'latest'"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent ID"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project path"),
    mode: str = typer.Option("handoff", "--mode", "-m", help="Switch mode: handoff|clone|skills-only"),
    no_skills: bool = typer.Option(False, "--no-skills", help="Do not transfer skills"),
    no_memory: bool = typer.Option(False, "--no-memory", help="Do not transfer memory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Display migration plan without launching native CLI"),
):
    """Switch to MiniMax Coding CLI (mcode) from another provider, or launch mcode directly."""
    _execute_provider_switch("minimax", from_provider, session, agent, project, mode, no_skills, no_memory, dry_run, extra_args=ctx.args)


@app.command("dsh", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def switch_to_dsh(
    ctx: typer.Context,
    from_provider: Optional[str] = typer.Option(None, "--from", "-f", help="Source agent/provider platform"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID or 'latest'"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent ID"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project path"),
    mode: str = typer.Option("handoff", "--mode", "-m", help="Switch mode: handoff|clone|skills-only"),
    no_skills: bool = typer.Option(False, "--no-skills", help="Do not transfer skills"),
    no_memory: bool = typer.Option(False, "--no-memory", help="Do not transfer memory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Display migration plan without launching native CLI"),
):
    """Switch to DeepSeek Shell (DSH) from another provider, or launch dsh directly."""
    _execute_provider_switch("dsh", from_provider, session, agent, project, mode, no_skills, no_memory, dry_run, extra_args=ctx.args)


@app.command("pi", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def switch_to_pi(
    ctx: typer.Context,
    from_provider: Optional[str] = typer.Option(None, "--from", "-f", help="Source agent/provider platform"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID or 'latest'"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent ID"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project path"),
    mode: str = typer.Option("handoff", "--mode", "-m", help="Switch mode: handoff|clone|skills-only"),
    no_skills: bool = typer.Option(False, "--no-skills", help="Do not transfer skills"),
    no_memory: bool = typer.Option(False, "--no-memory", help="Do not transfer memory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Display migration plan without launching native CLI"),
):
    """Switch to Pi Coding Agent (pi) from another provider, or launch pi directly."""
    _execute_provider_switch("pi", from_provider, session, agent, project, mode, no_skills, no_memory, dry_run, extra_args=ctx.args)



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
