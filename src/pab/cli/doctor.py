"""Doctor health check command."""

import json
from rich.console import Console
from rich.table import Table
import typer

from pab.core.config import ConfigManager
from pab.providers.detector import ProviderRegistry

doctor_app = typer.Typer(help="System and provider health checks")
console = Console()


@doctor_app.callback(invoke_without_command=True)
def doctor(
    as_json: bool = typer.Option(False, "--json", help="Output health report as JSON"),
):
    """Run comprehensive diagnostic health checks across all AI agent platforms."""
    config = ConfigManager()
    registry = ProviderRegistry(workspace_root=config.root.parent)
    detected = registry.detect_all()

    report = {
        "pab_home": str(config.root),
        "db_status": "ok" if config.db_path.is_file() else "initialized",
        "providers": detected,
    }

    if as_json:
        console.print(json.dumps(report, indent=2))
        return

    console.print(f"[bold cyan]PersonaOS Agent Bridge (PAB) Doctor[/bold cyan]")
    console.print(f"PAB Storage: [dim]{config.root}[/dim]\n")

    table = Table(title="Provider Diagnostic Matrix")
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Display Name", style="white")
    table.add_column("Installed", style="green")
    table.add_column("Version", style="yellow")
    table.add_column("Capabilities", style="magenta")

    for name, data in detected.items():
        status = "✅ Detected" if data["detected"] else "❌ Not Found"
        version = data["version"] or "N/A"
        caps = ", ".join(k for k, v in data["capabilities"].items() if v is True) or "None"
        table.add_row(name, data["display_name"], status, version, caps)

    console.print(table)
