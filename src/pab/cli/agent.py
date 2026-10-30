"""Agent Registry CLI commands."""

import json
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
import typer
import yaml

from pab.core.models.agent import (
    AgentCapabilities,
    AgentIdentity,
    AgentInstructions,
    AgentPreferences,
    CanonicalAgentDefinition,
)
from pab.registry.agent_registry import AgentRegistry

agent_app = typer.Typer(help="Manage canonical agent profiles and deployments")
console = Console()


@agent_app.command("list")
def list_agents(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all canonical agents."""
    reg = AgentRegistry()
    agents = reg.list_agents()

    if as_json:
        console.print(json.dumps([a.model_dump() for a in agents], indent=2))
        return

    table = Table(title="Canonical Agent Registry")
    table.add_column("Agent ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Role", style="magenta")
    table.add_column("Version", style="yellow")
    table.add_column("Skills", style="green")

    for p in agents:
        a = p.agent
        table.add_row(
            a.id,
            a.name,
            a.identity.role,
            a.version,
            ", ".join(a.capabilities.skills) or "—",
        )

    console.print(table)


@agent_app.command("show")
def show_agent(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Display canonical agent profile details."""
    reg = AgentRegistry()
    profile = reg.get_agent(agent_id)
    if not profile:
        console.print(f"[red]Error: Agent '{agent_id}' not found.[/red]")
        raise typer.Exit(1)

    if as_json:
        console.print(json.dumps(profile.model_dump(), indent=2))
        return

    console.print(yaml.safe_dump(profile.model_dump(), sort_keys=False))


@agent_app.command("create")
def create_agent(
    agent_id: str = typer.Argument(..., help="Unique agent identifier"),
    name: Optional[str] = typer.Option(None, "--name", help="Display name"),
    role: Optional[str] = typer.Option(None, "--role", help="Agent role"),
    description: Optional[str] = typer.Option(None, "--desc", help="Short description"),
    skills: Optional[str] = typer.Option(None, "--skills", help="Comma-separated skill names"),
):
    """Create a new canonical agent profile."""
    reg = AgentRegistry()
    skill_list = [s.strip() for s in skills.split(",")] if skills else []

    definition = CanonicalAgentDefinition(
        id=agent_id,
        name=name or agent_id.replace("-", " ").title(),
        description=description or f"Autonomous {role or agent_id}",
        identity=AgentIdentity(
            role=role or agent_id.replace("-", " ").title(),
            objective=f"Assist with {role or agent_id} duties",
        ),
        capabilities=AgentCapabilities(skills=skill_list),
    )

    try:
        profile = reg.create_agent(definition)
        console.print(f"[green]Successfully created canonical agent:[/green] [bold]{profile.agent.name}[/bold] ({profile.agent.id})")
    except Exception as e:
        console.print(f"[red]Error creating agent:[/red] {e}")
        raise typer.Exit(1)


@agent_app.command("import")
def import_agent(
    agent_id: str = typer.Argument(..., help="Agent ID on the provider (e.g. 'main', 'devops')"),
    provider: str = typer.Option("openclaw", "--from", "-f", help="Source provider platform (openclaw|agy|codex|claude)"),
    target_id: Optional[str] = typer.Option(None, "--as", help="Optional new canonical agent ID"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Import an existing native agent from a provider into the canonical PAB registry."""
    reg = AgentRegistry()
    try:
        profile = reg.import_native_agent(provider, agent_id, target_id=target_id)
        if as_json:
            console.print(json.dumps(profile.model_dump(mode="json"), indent=2))
            return
        console.print(f"[green]Successfully imported native agent into canonical registry:[/green] [bold]{profile.agent.name}[/bold] ({profile.agent.id})")
        console.print(f"Role: {profile.agent.identity.role}")
        if profile.agent.capabilities.skills:
            console.print(f"Skills ({len(profile.agent.capabilities.skills)}): {', '.join(profile.agent.capabilities.skills[:6])}...")
        console.print(f"Model: {profile.agent.preferences.model}")
        console.print(f"Source Platform: {provider}")
    except Exception as e:
        console.print(f"[red]Import failed:[/red] {e}")
        raise typer.Exit(1)


@agent_app.command("clone")
def clone_agent(
    source_id: str = typer.Argument(..., help="Source agent ID"),
    new_id: str = typer.Argument(..., help="New agent ID"),
    new_name: str = typer.Argument(..., help="New agent display name"),
):
    """Clone an existing agent into a new identity."""
    reg = AgentRegistry()
    try:
        cloned = reg.clone_agent(source_id, new_id, new_name)
        console.print(f"[green]Successfully cloned agent to:[/green] [bold]{cloned.agent.name}[/bold] ({cloned.agent.id})")
    except Exception as e:
        console.print(f"[red]Error cloning agent:[/red] {e}")
        raise typer.Exit(1)


@agent_app.command("deploy")
def deploy_agent(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    target: str = typer.Option("all", "--to", help="Target provider (openclaw|agy|codex|claude|all)"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Compile and deploy a canonical agent to selected native platforms."""
    reg = AgentRegistry()
    targets = [t.strip() for t in target.split(",")]
    results = reg.deploy_agent(agent_id, targets)

    if as_json:
        console.print(json.dumps(results, indent=2))
        return

    console.print(f"\n[bold]Deployment Results for [cyan]{agent_id}[/cyan]:[/bold]")
    for p, r in results.items():
        if r.get("success"):
            console.print(f"  ✅ [green]{p}[/green]: Deployed successfully")
            for w in r.get("warnings", []):
                console.print(f"     ⚠️ [yellow]Warning:[/yellow] {w}")
        else:
            console.print(f"  ❌ [red]{p}[/red]: Failed - {r.get('error')}")


@agent_app.command("delete")
def delete_agent(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Remove a canonical agent profile from the registry."""
    reg = AgentRegistry()
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete canonical agent '{agent_id}'?")
        if not confirm:
            console.print("Operation cancelled.")
            return

    ok = reg.delete_agent(agent_id)
    if ok:
        console.print(f"[green]Agent '{agent_id}' deleted successfully.[/green]")
    else:
        console.print(f"[red]Agent '{agent_id}' not found.[/red]")


@agent_app.command("rollback")
def rollback_agent(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    version: str = typer.Option(..., "--version", "-v", help="Target version string"),
):
    """Rollback an agent to a previously committed version."""
    reg = AgentRegistry()
    try:
        profile = reg.rollback_agent(agent_id, version)
        console.print(f"[green]Successfully rolled back agent '{agent_id}' to version {version}[/green]")
    except Exception as e:
        console.print(f"[red]Rollback failed:[/red] {e}")
        raise typer.Exit(1)
