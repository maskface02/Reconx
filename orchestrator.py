"""
Pipeline orchestrator for reconx framework.
Manages phase execution and chaining.
"""
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path
from rich.live import Live
from rich.text import Text
from rich.panel import Panel

from core.workspace import Workspace
from core.logger import get_logger, reset_logger, tool_tracker
from core.models import PhaseOutput
from phases import (
    Phase1Discovery,
    Phase2Probing,
    Phase3Crawling,
    Phase4Enumeration,
    Phase5Scanning,
    Phase6Exploitation,
    FPFilter
)
from phases.base import PhaseException


# Phase display names
PHASE_NAMES = {
    1: "Subdomain & Asset Discovery",
    2: "HTTP Probing & Tech Fingerprinting",
    3: "URL & Endpoint Crawling",
    4: "Directory Enumeration & Parameter Discovery",
    5: "Vulnerability Scanning & Secret Hunting",
    "fp": "False Positive Filtering & Scoring",
    6: "Targeted Exploitation",
}


class PipelineOrchestrator:
    """Orchestrates the execution of reconnaissance phases."""
    
    def __init__(self, target: str, config: Dict[str, Any], 
                 console=None, force: bool = False):
        self.target = target
        self.config = config
        self.force = force
        self.console = console
        
        # Initialize workspace
        self.workspace = Workspace(target)
        self.workspace.create()
        
        # Initialize logger
        reset_logger()
        self.logger = get_logger(
            "reconx",
            log_file=self.workspace.get_log_file("orchestrator"),
            console=console
        )
        
        # Phase mapping
        self.phase_map = {
            1: Phase1Discovery,
            2: Phase2Probing,
            3: Phase3Crawling,
            4: Phase4Enumeration,
            5: Phase5Scanning,
            "fp": FPFilter,
            6: Phase6Exploitation,
        }
    
    async def run_pipeline(self, from_phase: int = 1,
                          to_phase: Optional[int] = None,
                          single_phase: Optional[int] = None) -> bool:
        """
        Run the full or partial pipeline.

        Args:
            from_phase: Start from this phase (1-6)
            to_phase: Stop at this phase (default: run all)
            single_phase: Run only this phase

        Returns:
            True if pipeline completed successfully
        """
        # Check for interrupted previous run BEFORE any logging
        next_runnable = self.workspace.get_next_runnable_phase()
        interrupted = self.workspace.get_interrupted_phase()

        # Auto-resume from next runnable phase for full pipeline runs
        if single_phase is None and not self.force and next_runnable is not None and next_runnable > from_phase:
            # User ran 'python3 main.py run' without specifying a phase
            # Auto-adjust to start from the next runnable phase
            if self.console:
                completed_phases = [p for p in range(1, next_runnable) if self.workspace.phase_completed(p)]
                if completed_phases or interrupted:
                    self.console.print("")
                    if interrupted:
                        phase_name = interrupted['phase_name']
                        self.console.print(
                            Panel(
                                f"[bold yellow]Previous run was interrupted![/bold yellow]\n\n"
                                f"Target: [bold]{interrupted['target']}[/bold]\n"
                                f"Stopped at: [bold]{phase_name}[/bold]\n\n"
                                f"[dim]Last log entries:[/dim]\n"
                                + "\n".join([self._format_log_entry(l) for l in interrupted['last_logs'][-5:] if l.strip()]),
                                title="[bold red]⚠ Interrupted Run[/bold red]",
                                border_style="yellow",
                                padding=(1, 2),
                            )
                        )
                        self.console.print("")

                    self.console.print(
                        f"[bold green]Auto-resuming from Phase {next_runnable}[/bold green] "
                        f"[dim](Phases 1-{next_runnable-1} already completed)[/dim]"
                    )
                    self.console.print("")

            # Adjust from_phase to the next runnable phase
            from_phase = next_runnable

        # NOW log the starting message (after interruption check)
        self.logger.info(
            f"Starting pipeline for {self.target}", silent=True,
            phases=[single_phase] if single_phase is not None else [1, 2, 3, 4, 5, "fp", 6],
            force=self.force
        )

        # Determine phases to run
        if single_phase is not None:
            phases = [single_phase]

            # Check if the requested phase can run based on existing output files
            if next_runnable is not None and single_phase > next_runnable and not self.force:
                # Show helpful error message
                if self.console:
                    self.console.print("")
                    self.console.print(
                        f"[bold red]Error:[/bold red] Phase {single_phase} cannot run yet. "
                        f"Required phase output files are missing."
                    )
                    self.console.print("")
                    self.console.print(
                        f"[bold yellow]Suggestion:[/bold yellow] The next runnable phase is "
                        f"[bold green]Phase {next_runnable}[/bold green]. Run:"
                    )
                    self.console.print(
                        f"  [cyan]python3 main.py run --phase {next_runnable}[/cyan]"
                    )
                    self.console.print("")
                    self.console.print(
                        f"[dim]Or start from Phase {next_runnable} to run the remaining chain:[/dim]"
                    )
                    self.console.print(
                        f"  [cyan]python3 main.py run --from-phase {next_runnable}[/cyan]"
                    )
                    self.console.print(
                        f"[dim](Use --force to skip dependency checks)[/dim]"
                    )
                return False
        else:
            phases = [1, 2, 3, 4, 5, "fp", 6]
            if to_phase:
                phases = [p for p in phases if (isinstance(p, int) and p <= to_phase) or p == "fp"]

        self.logger.info(
            f"Starting pipeline for {self.target}", silent=True,
            phases=phases,
            force=self.force
        )
        
        for phase_key in phases:
            # Skip phases before from_phase
            if isinstance(phase_key, int) and phase_key < from_phase:
                self.logger.info(f"Skipping Phase {phase_key} (before --from-phase)", silent=True)
                continue
            
            # Get phase class
            PhaseClass = self.phase_map.get(phase_key)
            if not PhaseClass:
                self.logger.error(f"Unknown phase: {phase_key}")
                continue
            
            # Check if phase should be skipped (cached output)
            if not self.force and isinstance(phase_key, int):
                if self.workspace.phase_completed(phase_key):
                    self.logger.info(
                        f"Phase {phase_key} already completed (use --force to re-run)"
                    )
                    continue
            
            # Get phase name for display
            phase_name = PHASE_NAMES.get(phase_key, f"Phase {phase_key}")

            # Show phase separator
            if self.console:
                width = 70
                left_pad = (width - len(phase_name) - 6) // 2
                separator = "━" * max(left_pad, 2)
                self.console.print("")
                self.console.print(
                    f"[bold cyan]{separator}▶[/bold cyan] [bold green]Phase {phase_key}: {phase_name}[/bold green] [bold cyan]◀{separator}[/bold cyan]"
                )

            # Reset tool tracker for this phase
            tool_tracker.reset()

            # Run phase with live tool status
            self.logger.set_phase_context(
                phase=str(phase_key),
                target=self.target
            )

            try:
                phase = PhaseClass(self.workspace, self.config)
                if self.console:
                    async def _update_status():
                        """Background task to refresh the live display."""
                        while True:
                            await asyncio.sleep(0.3)
                            if live:
                                live.update(tool_tracker.render())

                    live = None  # Will be set by context manager
                    with Live(tool_tracker.render(), console=self.console,
                              refresh_per_second=3, transient=False) as live_display:
                        live = live_display
                        status_task = asyncio.create_task(_update_status())
                        try:
                            output = await phase.run()
                        finally:
                            status_task.cancel()
                else:
                    output = await phase.run()

                self.logger.info(
                    f"Phase {phase_key} complete", silent=True,
                    output_file=output.output_file,
                    count=output.count
                )

                # Show phase completion
                if self.console:
                    self.console.print(f"  [green]✓[/green] [dim]{phase_name}[/dim] — [bold]{output.count} items[/bold]")

                # Auto-generate phase report
                if isinstance(phase_key, int):
                    self._generate_phase_report(phase_key)


            except PhaseException as e:
                error_msg = str(e)
                self.logger.error(f"Phase {phase_key} failed: {error_msg}", silent=True)
                
                # Show error in console
                if self.console:
                    self.console.print("")
                    self.console.print(
                        Panel(
                            f"[bold red]{error_msg}[/bold red]",
                            title=f"[bold red]Phase {phase_key} Failed[/bold red]",
                            border_style="red",
                            padding=(1, 2),
                        )
                    )
                return False
            except Exception as e:
                self.logger.error(f"Unexpected error in Phase {phase_key}: {e}", silent=True)
                import traceback
                self.logger.debug(traceback.format_exc(), silent=True)
                return False

            # Special handling for FP filter phase
            if phase_key == "fp":
                review_size = self.workspace.review_queue_size()
                if review_size > 0:
                    self.logger.warning(
                        f"{review_size} findings need manual review.", silent=True
                    )
                    self.logger.warning(
                        f"Run: reconx review then re-run from phase 6.", silent=True
                    )
                    return True  # Not a failure, just needs review

        self.logger.info("Pipeline completed successfully", silent=True)
        return True
    
    async def run_phase(self, phase_number: int) -> bool:
        """Run a single phase."""
        return await self.run_pipeline(single_phase=phase_number)

    def get_status(self) -> Dict[str, Any]:
        """Get current workspace status."""
        return self.workspace.get_status()

    def _generate_phase_report(self, phase: int) -> None:
        """Auto-generate HTML and Markdown reports after phase completion."""
        try:
            from reports.generator import ReportGenerator
            gen = ReportGenerator(self.workspace)
            report_dir = Path("reports")
            report_dir.mkdir(exist_ok=True)

            # HTML report
            html_path = report_dir / f"{self.target}_phase{phase}_report.html"
            gen.generate_phase_html(phase, str(html_path))

            # Markdown report
            md_path = report_dir / f"{self.target}_phase{phase}_report.md"
            gen.generate_phase_markdown(phase, str(md_path))

            self.logger.info(f"Reports generated: {html_path}, {md_path}")
        except Exception as e:
            self.logger.debug(f"Failed to generate phase {phase} report: {e}")

    def _format_log_entry(self, log_line: str) -> str:
        """Format a JSON log entry for display."""
        try:
            import json
            entry = json.loads(log_line)
            level = entry.get('level', 'INFO')
            message = entry.get('message', '')
            tool = entry.get('tool', '')
            
            # Colorize based on level
            level_color = {
                'INFO': 'dim',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'DEBUG': 'dim white'
            }.get(level, 'dim')
            
            if tool:
                return f"[{level_color}]{level}[/{level_color}] {message} [dim]({tool})[/dim]"
            return f"[{level_color}]{level}[/{level_color}] {message}"
        except (json.JSONDecodeError, ValueError):
            return f"[dim]{log_line[:100]}[/dim]"


async def run_pipeline(
    target: str,
    config: Dict[str, Any],
    from_phase: int = 1,
    to_phase: Optional[int] = None,
    single_phase: Optional[int] = None,
    force: bool = False,
    console=None
) -> bool:
    """
    Convenience function to run the pipeline.
    
    Args:
        target: Target domain
        config: Configuration dictionary
        from_phase: Start from this phase
        to_phase: Stop at this phase
        single_phase: Run only this phase
        force: Force re-run even if output exists
        console: Rich console for output
    
    Returns:
        True if successful
    """
    orchestrator = PipelineOrchestrator(target, config, console, force)
    return await orchestrator.run_pipeline(from_phase, to_phase, single_phase)
