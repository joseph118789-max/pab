"""Provider agent launch interface."""

import subprocess
from pathlib import Path
from typing import Optional
from rich.console import Console
import typer

from pab.core.config import ConfigManager
from pab.providers.detector import ProviderRegistry
from pab.registry.agent_registry import AgentRegistry

run_app = typer.Typer(help="Unified provider agent launch")
console = Console()


@run_app.callback(invoke_without_command=True)
def run_agent(
    agent_id: str = typer.Argument(..., help="Agent ID to run"),
    provider_name: str = typer.Option("openclaw", "--provider", "-p", help="Target provider (openclaw|agy|codex|claude)"),
    handoff_session: Optional[str] = typer.Option(None, "--with-handoff", help="Optional session ID to inject handoff context before launch"),
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

    # Auto-deploy if not present on provider
    existing = provider.get_agent(agent_id)
    if not existing:
        console.print(f"[yellow]Agent '{agent_id}' not yet deployed to {provider.display_name}. Auto-deploying...[/yellow]")
        provider.create_agent(agent_profile.agent)

    # Inject handoff context if requested
    if handoff_session:
        from pab.sessions.manager import SessionMigrationManager
        sm = SessionMigrationManager(config)
        sm.import_context(provider_name, handoff_session)
        console.print(f"[green]Injected portable handoff context from session {handoff_session}[/green]")

    console.print(f"[bold green]Ready to launch '{agent_profile.agent.name}' on {provider.display_name}![/bold green]")
    console.print(f"Platform: {provider.display_name} (Version: {provider.version() or 'Detected'})")
    console.print(f"Agent: {agent_profile.agent.name} (Role: {agent_profile.agent.identity.role})")
