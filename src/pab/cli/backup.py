"""Backup and rollback CLI commands."""

import shutil
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
import typer

from pab.core.config import ConfigManager

backup_app = typer.Typer(help="Backup, audit, and recovery")
console = Console()


@backup_app.command("list")
def list_backups():
    """List available configuration and memory backup archives."""
    config = ConfigManager()
    table = Table(title="PAB Snapshot Backups")
    table.add_column("Backup Name", style="cyan")
    table.add_column("Path", style="dim")

    for b in config.backups_dir.iterdir():
        if b.is_dir():
            table.add_row(b.name, str(b))

    console.print(table)


@backup_app.command("create")
def create_backup():
    """Create a complete snapshot of all PAB agents, memory, skills, and configuration."""
    config = ConfigManager()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    dest = config.backups_dir / f"full_backup_{timestamp}"
    dest.mkdir(parents=True, exist_ok=True)

    for item in [config.agents_dir, config.skills_dir, config.memory_dir, config.instructions_dir]:
        if item.is_dir():
            shutil.copytree(item, dest / item.name)

    console.print(f"[green]Full PAB backup created successfully at:[/green] {dest}")
