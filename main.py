#!/usr/bin/env python3
"""
reconx - Modular Penetration Testing Framework
CLI entry point for the reconx framework.
"""
import asyncio
import sys
import webbrowser
from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# Ensure core modules are importable
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator import PipelineOrchestrator, run_pipeline
from core.workspace import Workspace
from core.logger import get_logger
from tui.review_queue import launch_review_tui
from reports.generator import ReportGenerator


console = Console()


def show_banner(console_obj: Console):
    """Display the R3c0nX banner inline (no external file)."""
    from rich.text import Text
    banner_raw = (
        " $$$$$$$\\   $$$$$$\\             $$$$$$\\            $$\\   $$\\ \n"
        " $$  __$$\\ $$ ___$$\\           $$$ __$$\\           $$ |  $$ |\n"
        " $$ |  $$ |\\_/   $$ | $$$$$$$\\ $$$$\\ $$ |$$$$$$$\\  \\$$\\ $$  |\n"
        " $$$$$$$  |  $$$$$ / $$  _____|$$\\$$\\$$ |$$  __$$\\  \\$$$$  / \n"
        " $$  __$$<   \\___$$\\ $$ /      $$ \\$$$$ |$$ |  $$ | $$  $$< \n"
        " $$ |  $$ |$$\\   $$ |$$ |      $$ |\\$$$ |$$ |  $$ |$$  /\\$$\\\n"
        " $$ |  $$ |\\$$$$$$  |\\$$$$$$$\\ \\$$$$$$  /$$ |  $$ |$$ /  $$ |\n"
        " \\__|  \\__| \\______/  \\_______| \\______/ \\__|  \\__|\\__|  \\__|\n"
    )
    banner_text = Text(banner_raw)
    banner_text.stylize("bold green")
    console_obj.print(banner_text)

    console_obj.print(
        Panel(
            "[bold green]R3c0nX[/bold green] — [dim]Unified Reconnaissance Framework[/dim]\n"
            "[dim]https://github.com/maskface02/reconx[/dim]",
            border_style="green",
            padding=(0, 2),
        )
    )
    console_obj.print("")


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


@click.group()
@click.version_option(version="1.0.0", prog_name="reconx")
def cli():
    """reconx - Modular Penetration Testing Framework"""
    pass


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--phase', '-p', type=int, help='Run specific phase only (1-6)')
@click.option('--from-phase', type=int, default=1, help='Start from this phase')
@click.option('--to-phase', type=int, help='Stop at this phase')
@click.option('--force', '-f', is_flag=True, help='Force re-run even if output exists')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
def run(
    config: str,
    phase: Optional[int],
    from_phase: int,
    to_phase: Optional[int],
    force: bool,
    verbose: bool
):
    """Run the reconnaissance pipeline."""
    # Display banner
    show_banner(console)

    # Load configuration
    try:
        cfg = load_config(config)
    except FileNotFoundError:
        console.print(f"[red]Configuration file not found: {config}[/red]")
        console.print("[yellow]Run 'reconx init' to create a config template[/yellow]")
        sys.exit(1)
    except yaml.YAMLError as e:
        console.print(f"[red]Error parsing configuration: {e}[/red]")
        sys.exit(1)

    # Validate target
    target = cfg.get('target')
    if not target:
        console.print("[red]No 'target' specified in config file.[/red]")
        sys.exit(1)

    # Build config summary
    rate_limit = cfg.get('rate_limit', 50)
    threads = cfg.get('threads', 20)
    scope = cfg.get('scope', [])
    exclude = cfg.get('exclude', [])
    chaos_set = bool(cfg.get('chaos_api_key'))
    github_set = bool(cfg.get('github_token'))

    summary = Table.grid(padding=(0, 2))
    summary.add_column("Key", style="bold cyan")
    summary.add_column("Value", style="bold white")
    summary.add_row("Target", target)
    summary.add_row("Scope", ", ".join(scope) if scope else "[dim]* (all)[/dim]")
    summary.add_row("Exclude", ", ".join(exclude) if exclude else "[dim]None[/dim]")
    summary.add_row("Rate Limit", str(rate_limit))
    summary.add_row("Threads", str(threads))
    summary.add_row("Chaos API", "[green]Yes[/green]" if chaos_set else "[red]No[/red]")
    summary.add_row("GitHub Token", "[green]Yes[/green]" if github_set else "[red]No[/red]")

    console.print(Panel(summary, title="[bold green]Configuration[/bold green]", border_style="green", padding=(0, 1)))
    console.print("")

    # Phase info
    phase_label = f"Phase {phase}" if phase else f"Phase {from_phase}{'-'+str(to_phase) if to_phase else '-6'}"
    force_note = " [bold yellow](force)[/bold yellow]" if force else ""
    console.print(f"  [dim]Phases:[/dim] {phase_label}{force_note}")
    console.print(f"  [dim]Config:[/dim] {config}")
    console.print("")

    # Set log level
    if verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    # Run pipeline
    console.print(f"[blue]Starting reconx for target: {target}[/blue]")

    success = asyncio.run(run_pipeline(
        target=target,
        config=cfg,
        from_phase=from_phase,
        to_phase=to_phase,
        single_phase=phase,
        force=force,
        console=console
    ))

    if success:
        console.print("")
        console.print(
            Panel(
                "[bold green]Pipeline completed successfully![/bold green]",
                border_style="green",
            )
        )
    else:
        console.print("")
        console.print(
            Panel(
                "[bold red]Pipeline failed![/bold red]",
                border_style="red",
            )
        )
        sys.exit(1)


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
def review(config: str):
    """Open manual review queue for a target."""
    try:
        cfg = load_config(config)
    except (FileNotFoundError, yaml.YAMLError):
        console.print("[red]Config file not found or invalid. Run 'reconx init'[/red]")
        sys.exit(1)

    target = cfg.get('target')
    if not target:
        console.print("[red]No 'target' specified in config file.[/red]")
        sys.exit(1)

    launch_review_tui(target)


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--format', '-f', 'output_format',
              type=click.Choice(['json', 'html', 'markdown']),
              default='markdown',
              help='Report format')
@click.option('--phase', '-p', type=int, help='Generate report for specific phase only')
@click.option('--output', '-o', help='Output file path')
def report(config: str, output_format: str, phase: Optional[int], output: Optional[str]):
    """Generate findings report for a target or specific phase."""
    try:
        cfg = load_config(config)
    except (FileNotFoundError, yaml.YAMLError):
        console.print("[red]Config file not found or invalid. Run 'reconx init'[/red]")
        sys.exit(1)

    target = cfg.get('target')
    if not target:
        console.print("[red]No 'target' specified in config file.[/red]")
        sys.exit(1)

    workspace = Workspace(target)

    if not workspace.exists():
        console.print(f"[red]Workspace for {target} does not exist.[/red]")
        console.print(f"[yellow]Run: reconx run[/yellow]")
        sys.exit(1)

    generator = ReportGenerator(workspace)

    # Per-phase report
    if phase is not None:
        ext = 'html' if output_format == 'html' else 'md'
        if output is None:
            output = f"reports/{target}_phase{phase}_report.{ext}"

        Path(output).parent.mkdir(parents=True, exist_ok=True)

        try:
            if output_format == 'html':
                generator.generate_phase_html(phase, output)
                console.print(f"[green]Phase {phase} report generated: {output}[/green]")
                console.print("[dim]Opening in browser...[/dim]")
                webbrowser.open(Path(output).resolve().as_uri())
            elif output_format == 'markdown':
                generator.generate_phase_markdown(phase, output)
                console.print(f"[green]Phase {phase} report generated: {output}[/green]")
                with open(output, 'r') as f:
                    md_content = f.read()
                console.print("")
                console.print(Markdown(md_content))
            else:
                generator.generate_json(output)
                console.print(f"[green]Phase {phase} report generated: {output}[/green]")
        except Exception as e:
            console.print(f"[red]Error generating phase {phase} report: {e}[/red]")
            sys.exit(1)
        return

    # Full pipeline report
    if output is None:
        output = f"reports/{target}_report.{output_format}"

    Path(output).parent.mkdir(parents=True, exist_ok=True)

    try:
        if output_format == 'html':
            generator.generate_html(output)
            console.print(f"[green]Report generated: {output}[/green]")
            console.print("[dim]Opening in browser...[/dim]")
            webbrowser.open(Path(output).resolve().as_uri())
        elif output_format == 'markdown':
            generator.generate_markdown(output)
            console.print(f"[green]Report generated: {output}[/green]")
            with open(output, 'r') as f:
                md_content = f.read()
            console.print("")
            console.print(Markdown(md_content))
        else:
            generator.generate_json(output)
    except Exception as e:
        console.print(f"[red]Error generating report: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path (optional)')
def status(config: Optional[str]):
    """Show workspace status."""
    # Try to load config to get target
    target = None
    if config:
        try:
            cfg = load_config(config)
            target = cfg.get('target')
        except (FileNotFoundError, yaml.YAMLError):
            pass

    if target:
        # Show status for specific target
        workspace = Workspace(target)
        if not workspace.exists():
            console.print(f"[red]Workspace for {target} does not exist.[/red]")
            return

        status_data = workspace.get_status()

        table = Table(title=f"Workspace Status: {target}", box=box.DOUBLE_EDGE)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Target", status_data['target'])
        table.add_row("Workspace Path", status_data['workspace_path'])
        table.add_row("Phases Completed",
                     ", ".join(map(str, status_data['phases_completed'])))
        table.add_row("Confirmed Findings", str(status_data['findings']['confirmed']))
        table.add_row("Review Queue", str(status_data['findings']['review_queue']))
        table.add_row("Dropped Findings", str(status_data['findings']['dropped']))
        table.add_row("Exploit Results", str(status_data['findings']['exploits']))

        console.print(table)

        # Check for interrupted previous run
        interrupted = workspace.get_interrupted_phase()
        if interrupted:
            console.print("")
            console.print(
                Panel(
                    f"[bold yellow]Previous run was interrupted![/bold yellow]\n\n"
                    f"Target: [bold]{interrupted['target']}[/bold]\n"
                    f"Stopped at: [bold]{interrupted['phase_name']}[/bold]\n\n"
                    f"[dim]Run 'python3 main.py run' to resume from the next runnable phase.[/dim]",
                    title="[bold red]⚠ Interrupted Run[/bold red]",
                    border_style="yellow",
                    padding=(1, 2),
                )
            )

        # Show next runnable phase
        next_phase = workspace.get_next_runnable_phase()
        if next_phase is not None:
            console.print("")
            console.print(
                Panel(
                    f"Next runnable phase: [bold green]Phase {next_phase}[/bold green]\n\n"
                    f"Run: [cyan]python3 main.py run --phase {next_phase}[/cyan]\n"
                    f"Or: [cyan]python3 main.py run --from-phase {next_phase}[/cyan]",
                    title="[bold yellow]Next Action[/bold yellow]",
                    border_style="yellow",
                    padding=(1, 2),
                )
            )
        else:
            console.print("")
            console.print(
                Panel(
                    "[bold green]All phases completed![/bold green]\n"
                    "Use [cyan]--force[/cyan] to re-run phases.",
                    title="[bold yellow]Status[/bold yellow]",
                    border_style="green",
                    padding=(1, 2),
                )
            )
    else:
        # List all workspaces
        workspaces_dir = Path("./workspaces")
        if not workspaces_dir.exists():
            console.print("[yellow]No workspaces found.[/yellow]")
            return

        table = Table(title="All Workspaces", box=box.DOUBLE_EDGE)
        table.add_column("Target", style="cyan")
        table.add_column("Phases", style="green")
        table.add_column("Findings", style="yellow")

        for ws_dir in sorted(workspaces_dir.iterdir()):
            if ws_dir.is_dir():
                ws = Workspace(ws_dir.name)
                status_data = ws.get_status()
                phases = len(status_data['phases_completed'])
                findings = status_data['findings']['confirmed']
                table.add_row(
                    ws_dir.name,
                    f"{phases}/6",
                    str(findings)
                )

        console.print(table)


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.confirmation_option(prompt='Are you sure you want to clear this workspace?')
def clear(config: str):
    """Clear workspace for a target."""
    try:
        cfg = load_config(config)
    except (FileNotFoundError, yaml.YAMLError):
        console.print("[red]Config file not found or invalid. Run 'reconx init'[/red]")
        sys.exit(1)

    target = cfg.get('target')
    if not target:
        console.print("[red]No 'target' specified in config file.[/red]")
        sys.exit(1)

    workspace = Workspace(target)
    if workspace.exists():
        workspace.clear()
        console.print(f"[green]Workspace cleared for {target}[/green]")
    else:
        console.print(f"[yellow]Workspace for {target} does not exist.[/yellow]")


@cli.command()
def init():
    """Initialize a new config.yaml template."""
    config_template = '''# reconx Configuration Template

# Target domain
target: example.com

# Scope (subdomains to include)
scope:
  - "*.example.com"
  - "example.com"

# Exclusions (subdomains to exclude)
exclude:
  - "out-of-scope.example.com"

# Rate limiting
rate_limit: 50          # requests per second globally
threads: 20

# Wordlists
wordlist_dirs: /usr/share/seclists/Discovery/Web-Content/
wordlist_subs: /usr/share/seclists/Discovery/DNS/

# Tool paths (leave empty to use PATH)
tools:
  subfinder: subfinder
  amass: amass
  dnsx: dnsx
  httpx: httpx
  katana: katana
  ffuf: ffuf
  feroxbuster: feroxbuster
  paramspider: paramspider
  arjun: arjun
  nuclei: nuclei
  sqlmap: sqlmap
  dalfox: dalfox
  gf: gf
  secretfinder: secretfinder
  trufflehog: trufflehog
  wafw00f: wafw00f
  masscan: masscan
  nmap: nmap
  nikto: nikto
  waybackurls: waybackurls
  gau: gau
  gospider: gospider
  hakrawler: hakrawler
  linkfinder: linkfinder
  x8: x8
  xsstrike: xsstrike
  jwt_tool: jwt-tool
  gitdorker: gitdorker
  ghauri: ghauri

# Nuclei templates path
nuclei_templates: /usr/share/nuclei-templates/

# Optional: Interact.sh server for blind SSRF testing
interactsh_server: ""

# Optional: GitHub token for gitdorker
github_token: ""

# Optional: Chaos API key for subdomain discovery
chaos_api_key: ""
'''
    
    config_path = Path("config.yaml")
    if config_path.exists():
        console.print("[yellow]config.yaml already exists. Use --force to overwrite.[/yellow]")
        return
    
    with open(config_path, 'w') as f:
        f.write(config_template)
    
    console.print("[green]Created config.yaml template[/green]")
    console.print("[blue]Edit config.yaml with your target and settings, then run:[/blue]")
    console.print("  reconx run")


if __name__ == '__main__':
    cli()
