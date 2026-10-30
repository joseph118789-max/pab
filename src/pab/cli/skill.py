"""Skill Manager CLI commands."""

import json
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
import typer

from pab.skills.manager import SkillManager

skill_app = typer.Typer(help="Universal Open Agent Skills management")
console = Console()


@skill_app.command("list")
def list_skills(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all canonical skills in the library."""
    sm = SkillManager()
    skills = sm.list_skills()

    if as_json:
        console.print(json.dumps([s.model_dump() for s in skills], indent=2))
        return

    table = Table(title="Universal Skill Library (Open Agent Skills)")
    table.add_column("Skill Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Scripts", style="yellow")
    table.add_column("References", style="magenta")

    for s in skills:
        table.add_row(
            s.manifest.name,
            s.manifest.description[:60] + ("..." if len(s.manifest.description) > 60 else ""),
            str(len(s.scripts)),
            str(len(s.references)),
        )

    console.print(table)


@skill_app.command("create")
def create_skill(
    name: str = typer.Argument(..., help="Skill name in kebab-case"),
    description: str = typer.Option(..., "--desc", "-d", help="Skill description"),
):
    """Create a new Open Agent Skill template."""
    sm = SkillManager()
    try:
        skill = sm.create_skill(name, description)
        console.print(f"[green]Created canonical skill:[/green] [bold]{skill.manifest.name}[/bold]")
    except Exception as e:
        console.print(f"[red]Error creating skill:[/red] {e}")
        raise typer.Exit(1)


@skill_app.command("import")
def import_skill(
    source_path: str = typer.Argument(..., help="Path to local skill directory"),
):
    """Import an existing skill folder containing SKILL.md into the canonical library."""
    sm = SkillManager()
    p = Path(source_path)
    try:
        imported = sm.import_skill(p)
        console.print(f"[green]Successfully imported skill:[/green] [bold]{imported.manifest.name}[/bold]")
    except Exception as e:
        console.print(f"[red]Import failed:[/red] {e}")
        raise typer.Exit(1)


@skill_app.command("export")
def export_skill(
    name: str = typer.Argument(..., help="Skill name"),
    target_dir: str = typer.Option(".", "--to", help="Target export directory"),
):
    """Export a canonical skill package."""
    sm = SkillManager()
    try:
        dest = sm.export_skill(name, Path(target_dir))
        console.print(f"[green]Exported skill '{name}' to:[/green] {dest}")
    except Exception as e:
        console.print(f"[red]Export failed:[/red] {e}")
        raise typer.Exit(1)


@skill_app.command("validate")
def validate_skill(
    name: str = typer.Argument(..., help="Skill name"),
):
    """Validate a skill against Open Agent Skills specifications."""
    sm = SkillManager()
    try:
        issues = sm.validate_skill(name)
        if not issues:
            console.print(f"[green]Skill '{name}' passed validation with no issues![/green]")
        else:
            console.print(f"[yellow]Validation issues found for '{name}':[/yellow]")
            for issue in issues:
                console.print(f"  - ⚠️ {issue}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@skill_app.command("audit")
def audit_skill(
    name: str = typer.Argument(..., help="Skill name"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Run security audit on skill instructions and scripts."""
    sm = SkillManager()
    try:
        report = sm.audit_skill(name)
        if as_json:
            console.print(json.dumps(report, indent=2))
            return

        if report["is_safe"]:
            console.print(f"[green]Security Audit Passed: Skill '{name}' is clean (0 findings).[/green]")
        else:
            console.print(f"[red]Security Warnings for '{name}' ({report['findings_count']} issues):[/red]")
            for f in report["findings"]:
                console.print(f"  - [{f['type']}] in {f['target']}: {f['detail']}")
    except Exception as e:
        console.print(f"[red]Audit failed:[/red] {e}")
        raise typer.Exit(1)


@skill_app.command("deploy")
def deploy_skill(
    name: str = typer.Argument(..., help="Skill name"),
    target: str = typer.Option("all", "--to", help="Target providers (comma-separated or 'all')"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Deploy a skill to selected provider platforms."""
    sm = SkillManager()
    targets = [t.strip() for t in target.split(",")]
    results = sm.deploy_skill(name, targets)

    if as_json:
        console.print(json.dumps(results, indent=2))
        return

    console.print(f"\n[bold]Skill Deployment for [cyan]{name}[/cyan]:[/bold]")
    for p, r in results.items():
        if r.get("success"):
            console.print(f"  ✅ [green]{p}[/green]: Installed")
        else:
            console.print(f"  ❌ [red]{p}[/red]: Failed - {r.get('error')}")


@skill_app.command("sync")
def sync_skills(
    target: str = typer.Option("all", "--to", help="Target providers"),
):
    """Synchronise all library skills to provider platforms."""
    sm = SkillManager()
    targets = [t.strip() for t in target.split(",")]
    results = sm.sync_skills(targets)
    console.print(f"[green]Synchronised {len(results)} skills across providers.[/green]")
