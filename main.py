#!/usr/bin/env python3
"""
reconx - Modular Penetration Testing Framework
CLI entry point for the reconx framework.
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich import box

# Ensure core modules are importable
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator import PipelineOrchestrator, run_pipeline
from core.workspace import Workspace
from core.logger import get_logger
from tui.review_queue import launch_review_tui
from reports.generator import ReportGenerator


console = Console()


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
@click.option('--target', '-t', required=True, help='Target domain')
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--phase', '-p', type=int, help='Run specific phase only (1-6)')
@click.option('--from-phase', type=int, default=1, help='Start from this phase')
@click.option('--to-phase', type=int, help='Stop at this phase')
@click.option('--force', '-f', is_flag=True, help='Force re-run even if output exists')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
def run(
    target: str,
    config: str,
    phase: Optional[int],
    from_phase: int,
    to_phase: Optional[int],
    force: bool,
    verbose: bool
):
    """Run the reconnaissance pipeline."""
    # Load configuration
    try:
        cfg = load_config(config)
        cfg['target'] = target  # Override target from CLI
    except FileNotFoundError:
        console.print(f"[red]Configuration file not found: {config}[/red]")
        console.print("[yellow]Using default configuration[/yellow]")
        cfg = {
            'target': target,
            'scope': [f"*.{target}", target],
            'exclude': [],
            'rate_limit': 50,
            'threads': 20,
            'timeout': 10,
            'tools': {}
        }
    except yaml.YAMLError as e:
        console.print(f"[red]Error parsing configuration: {e}[/red]")
        sys.exit(1)
    
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
        console.print(f"[green]Pipeline completed successfully![/green]")
    else:
        console.print(f"[red]Pipeline failed![/red]")
        sys.exit(1)


@cli.command()
@click.option('--target', '-t', required=True, help='Target domain')
def review(target: str):
    """Open manual review queue for a target."""
    launch_review_tui(target)


@cli.command()
@click.option('--target', '-t', required=True, help='Target domain')
@click.option('--format', '-f', 'output_format', 
              type=click.Choice(['json', 'html', 'markdown']), 
              default='markdown',
              help='Report format')
@click.option('--output', '-o', help='Output file path')
def report(target: str, output_format: str, output: Optional[str]):
    """Generate findings report for a target."""
    workspace = Workspace(target)
    
    if not workspace.exists():
        console.print(f"[red]Workspace for {target} does not exist.[/red]")
        console.print(f"[yellow]Run: reconx run --target {target}[/yellow]")
        sys.exit(1)
    
    generator = ReportGenerator(workspace)
    
    if output is None:
        output = f"reconx_report_{target}.{output_format}"
    
    try:
        if output_format == 'json':
            generator.generate_json(output)
        elif output_format == 'html':
            generator.generate_html(output)
        else:
            generator.generate_markdown(output)
        
        console.print(f"[green]Report generated: {output}[/green]")
    except Exception as e:
        console.print(f"[red]Error generating report: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--target', '-t', help='Target domain (optional)')
def status(target: Optional[str]):
    """Show workspace status."""
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
@click.option('--target', '-t', required=True, help='Target domain')
@click.confirmation_option(prompt='Are you sure you want to clear this workspace?')
def clear(target: str):
    """Clear workspace for a target."""
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
timeout: 10             # seconds per request

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
  ssrfire: ssrfire
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
    console.print("  reconx run --target example.com --config config.yaml")


if __name__ == '__main__':
    cli()
