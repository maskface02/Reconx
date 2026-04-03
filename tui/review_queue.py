"""
Manual Review TUI using Rich library.
Interactive terminal UI for reviewing findings.
"""
import json
from typing import List, Optional, Dict, Any
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt
from rich import box

from core.workspace import Workspace
from core.models import Finding


class ReviewQueueTUI:
    """Interactive TUI for manual review of findings."""
    
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.console = Console()
        self.findings: List[Finding] = []
        self.current_index = 0
        self.stats = {
            "confirmed": 0,
            "rejected": 0,
            "skipped": 0
        }
    
    def run(self) -> None:
        """Run the interactive review TUI."""
        # Load review queue
        self.findings = self.workspace.load_findings("review_queue.json")
        
        if not self.findings:
            self.console.print("[yellow]No findings in review queue.[/yellow]")
            return
        
        self.console.print(f"[green]Loaded {len(self.findings)} findings for review[/green]")
        
        # Load existing stats if available
        self._load_progress()
        
        # Main review loop
        while self.current_index < len(self.findings):
            finding = self.findings[self.current_index]
            
            # Clear screen and display finding
            self.console.clear()
            self._display_finding(finding)
            
            # Get user action
            action = self._get_action()
            
            if action == 'C':
                self._confirm_finding(finding)
            elif action == 'R':
                self._reject_finding(finding)
            elif action == 'S':
                self._skip_finding(finding)
            elif action == 'Q':
                self._save_progress()
                self.console.print("[yellow]Review queue saved. Exiting.[/yellow]")
                return
            elif action == 'P':
                if self.current_index > 0:
                    self.current_index -= 1
                continue
            
            self.current_index += 1
        
        # Review complete
        self.console.clear()
        self._display_summary()
        self._save_progress()
    
    def _display_finding(self, finding: Finding) -> None:
        """Display a finding in the TUI."""
        # Create layout
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="actions", size=5)
        )
        
        # Header with progress
        progress_text = (
            f"Finding {self.current_index + 1}/{len(self.findings)} | "
            f"Confirmed: {self.stats['confirmed']} | "
            f"Rejected: {self.stats['rejected']} | "
            f"Skipped: {self.stats['skipped']}"
        )
        layout["header"].update(
            Panel(progress_text, title="Review Queue", border_style="blue")
        )
        
        # Main content
        main_content = self._create_finding_panel(finding)
        layout["main"].update(main_content)
        
        # Actions
        actions_text = (
            "[C] Confirm → pass to Phase 6    [R] Reject → drop\n"
            "[S] Skip (decide later)          [P] Previous\n"
            "[Q] Quit & save queue"
        )
        layout["actions"].update(
            Panel(actions_text, title="Actions", border_style="green")
        )
        
        self.console.print(layout)
    
    def _create_finding_panel(self, finding: Finding) -> Layout:
        """Create the main finding display panel."""
        # Create table for finding details
        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column("Field", style="cyan", width=15)
        table.add_column("Value", style="white")
        
        table.add_row("Type", finding.vuln_type.upper())
        table.add_row("Severity", f"[{finding.severity}]{finding.severity.upper()}[/{finding.severity}]")
        table.add_row("Tool", finding.tool)
        table.add_row("Score", f"{finding.score}/100")
        table.add_row("URL", finding.url)
        if finding.param:
            table.add_row("Param", finding.param)
        if finding.template:
            table.add_row("Template", finding.template)
        
        # Score breakdown
        breakdown_text = self._format_breakdown(finding.score_breakdown)
        table.add_row("Breakdown", breakdown_text)
        
        # Create layout
        layout = Layout()
        layout.split_column(
            Layout(name="details"),
            Layout(name="request", size=8),
            Layout(name="response", size=10)
        )
        
        layout["details"].update(Panel(table, title="Finding Details", border_style="cyan"))
        
        # Request panel
        request_content = finding.request or "No request captured"
        layout["request"].update(
            Panel(request_content, title="Request", border_style="yellow")
        )
        
        # Response panel
        response_content = finding.response_snippet or "No response snippet captured"
        if len(response_content) > 500:
            response_content = response_content[:500] + "..."
        layout["response"].update(
            Panel(response_content, title="Response Snippet", border_style="magenta")
        )
        
        return layout
    
    def _format_breakdown(self, breakdown: Dict[str, Any]) -> str:
        """Format the score breakdown for display."""
        lines = []
        for key, value in breakdown.items():
            signal_value = self._get_signal_value(key)
            symbol = "✓" if signal_value > 0 else "✗"
            color = "green" if signal_value > 0 else "red"
            lines.append(f"[{color}]{symbol} {key} ({signal_value:+d})[/{color}]")
        
        if not lines:
            return "No scoring signals triggered"
        
        return "\n".join(lines)
    
    def _get_signal_value(self, signal_name: str) -> int:
        """Get the value of a scoring signal."""
        from phases.fp_filter import SIGNALS
        return SIGNALS.get(signal_name, 0)
    
    def _get_action(self) -> str:
        """Get user action input."""
        valid_actions = ['C', 'R', 'S', 'Q', 'P']
        while True:
            action = Prompt.ask(
                "Action",
                choices=valid_actions,
                default='S'
            ).upper()
            if action in valid_actions:
                return action
    
    def _confirm_finding(self, finding: Finding) -> None:
        """Confirm a finding and add to confirmed list."""
        finding.confirmed = True
        finding.confidence = "high"
        
        # Load existing confirmed findings
        confirmed = self.workspace.load_findings("confirmed_findings.json")
        confirmed.append(finding)
        self.workspace.save_findings(confirmed, "confirmed_findings.json")
        
        # Remove from review queue
        self._remove_from_queue(finding.id)
        
        self.stats["confirmed"] += 1
        self.console.print("[green]Finding confirmed[/green]")
    
    def _reject_finding(self, finding: Finding) -> None:
        """Reject a finding and add to dropped list."""
        finding.confirmed = False
        
        # Load existing dropped findings
        dropped = self.workspace.load_findings("dropped_findings.json")
        dropped.append(finding)
        self.workspace.save_findings(dropped, "dropped_findings.json")
        
        # Remove from review queue
        self._remove_from_queue(finding.id)
        
        self.stats["rejected"] += 1
        self.console.print("[red]Finding rejected[/red]")
    
    def _skip_finding(self, finding: Finding) -> None:
        """Skip a finding for later review."""
        self.stats["skipped"] += 1
        self.console.print("[yellow]Finding skipped[/yellow]")
    
    def _remove_from_queue(self, finding_id: str) -> None:
        """Remove a finding from the review queue."""
        self.findings = [f for f in self.findings if f.id != finding_id]
        self.current_index -= 1  # Adjust index since we removed an item
        self.workspace.save_findings(self.findings, "review_queue.json")
    
    def _save_progress(self) -> None:
        """Save review progress."""
        progress = {
            "current_index": self.current_index,
            "stats": self.stats
        }
        progress_file = self.workspace.workspace_path / "review_progress.json"
        with open(progress_file, 'w') as f:
            json.dump(progress, f, indent=2)
    
    def _load_progress(self) -> None:
        """Load previous review progress."""
        progress_file = self.workspace.workspace_path / "review_progress.json"
        if progress_file.exists():
            try:
                with open(progress_file, 'r') as f:
                    progress = json.load(f)
                    self.current_index = progress.get("current_index", 0)
                    self.stats = progress.get("stats", self.stats)
            except json.JSONDecodeError:
                pass
    
    def _display_summary(self) -> None:
        """Display review summary."""
        table = Table(title="Review Summary", box=box.DOUBLE_EDGE)
        table.add_column("Action", style="cyan")
        table.add_column("Count", style="green", justify="right")
        
        table.add_row("Confirmed", str(self.stats["confirmed"]))
        table.add_row("Rejected", str(self.stats["rejected"]))
        table.add_row("Skipped", str(self.stats["skipped"]))
        table.add_row("Total Reviewed", str(sum(self.stats.values())))
        
        self.console.print(table)
        
        if self.stats["confirmed"] > 0:
            self.console.print(
                f"\n[green]Run 'reconx run --from-phase 6' "
                f"to proceed with exploitation.[/green]"
            )


def launch_review_tui(target: str) -> None:
    """Launch the review TUI for a target."""
    from core.workspace import Workspace
    
    workspace = Workspace(target)
    if not workspace.exists():
        print(f"Workspace for {target} does not exist. Run reconnaissance first.")
        return
    
    tui = ReviewQueueTUI(workspace)
    tui.run()
