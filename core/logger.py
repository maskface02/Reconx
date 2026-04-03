"""
Structured logging for reconx framework.
"""
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from rich.console import Console


class StructuredLogger:
    """Structured logger for reconx framework."""
    
    def __init__(self, name: str, log_file: Optional[Path] = None,
                 console: Optional[Console] = None, level: int = logging.INFO):
        self.name = name
        self.log_file = log_file
        self.console = console or Console()
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.handlers = []

        # File handler for structured JSON logs
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
            self.logger.addHandler(file_handler)

        self.phase_context: Dict[str, Any] = {}
    
    def set_phase_context(self, phase: str, target: str, **kwargs):
        """Set context for the current phase."""
        self.phase_context = {
            "phase": phase,
            "target": target,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
    
    def _log(self, level: str, message: str, silent: bool = False, **extra):
        """Internal log method — writes structured JSON to file only."""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "logger": self.name,
            "message": message,
            **self.phase_context,
            **extra
        }

        # Log to file as JSON
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.emit(logging.makeLogRecord({
                    'name': self.name,
                    'level': getattr(logging, level.upper()),
                    'msg': json.dumps(log_data),
                    'args': (),
                }))

    def debug(self, message: str, **extra):
        self._log("DEBUG", message, **extra)

    def info(self, message: str, **extra):
        self._log("INFO", message, **extra)

    def warning(self, message: str, **extra):
        self._log("WARNING", message, **extra)

    def error(self, message: str, **extra):
        self._log("ERROR", message, **extra)

    def critical(self, message: str, **extra):
        self._log("CRITICAL", message, **extra)

    def tool_start(self, tool: str, command: str, **extra):
        """Log tool execution start (file only, no console)."""
        tool_tracker.start(tool)
        self._log("INFO", f"Starting tool: {tool}", silent=True,
                  tool=tool, command=command, event="tool_start", **extra)

    def tool_end(self, tool: str, output_file: Optional[str] = None,
                 item_count: int = 0, **extra):
        """Log tool execution end (file only, no console)."""
        tool_tracker.complete(tool, f"{item_count} items")
        self._log("INFO", f"Tool completed: {tool} ({item_count} items)", silent=True,
                  tool=tool, output_file=output_file,
                  item_count=item_count, event="tool_end", **extra)

    def tool_skipped(self, tool: str, reason: str, **extra):
        """Log tool skip (file only, no console)."""
        self._log("WARNING", f"Tool skipped: {tool} — {reason}", silent=True,
                  tool=tool, reason=reason, event="tool_skipped", **extra)
    
    def phase_start(self, phase: str, **extra):
        """Log phase start (file only — console handled by orchestrator)."""
        self._log("INFO", f"Phase {phase} started", silent=True,
                  phase=phase, event="phase_start", **extra)

    def phase_end(self, phase: str, output_file: str, item_count: int, **extra):
        """Log phase end (file only)."""
        self._log("INFO", f"Phase completed: {phase} ({item_count} items) → {output_file}",
                  silent=True,
                  phase=phase, output_file=output_file,
                  item_count=item_count, event="phase_end", **extra)
    
    def finding(self, finding_type: str, severity: str, url: str, **extra):
        """Log a finding discovery."""
        self.info(f"Finding: [{severity.upper()}] {finding_type} at {url}",
                  finding_type=finding_type, severity=severity, 
                  url=url, event="finding", **extra)


# Global logger instance
_logger: Optional[StructuredLogger] = None

# ── Tool Status Tracker (for live display) ──────────────────────────────────
class ToolStatusTracker:
    """Tracks running and completed tools for live status display."""
    def __init__(self):
        self._tools: Dict[str, str] = {}  # tool -> "running" or detail
        self._spinner_idx = 0

    def start(self, tool: str):
        self._tools[tool] = "running"

    def complete(self, tool: str, detail: str):
        self._tools[tool] = detail

    def reset(self):
        self._tools.clear()
        self._spinner_idx = 0

    def _next_spinner(self) -> str:
        """Cycle through spinner characters."""
        spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        char = spinners[self._spinner_idx % len(spinners)]
        self._spinner_idx += 1
        return char

    def render(self) -> str:
        running = [t for t, s in self._tools.items() if s == "running"]
        completed = [(t, s) for t, s in self._tools.items() if s != "running"]

        lines = []
        if running:
            spinner = self._next_spinner()
            lines.append(f"[bold cyan]{spinner}[/bold cyan] [dim]Running:[/dim] [white]{', '.join(running)}[/white]")
        for tool, status in completed[-10:]:
            lines.append(f"  [green]✓[/green] [dim]{tool}[/dim] — {status}")

        return "\n".join(lines) if lines else "[dim]Initializing...[/dim]"

tool_tracker = ToolStatusTracker()


def get_logger(name: str = "reconx", log_file: Optional[Path] = None,
               console: Optional[Console] = None) -> StructuredLogger:
    """Get or create the global logger instance."""
    global _logger
    if _logger is None:
        _logger = StructuredLogger(name, log_file, console)
    return _logger


def reset_logger():
    """Reset the global logger instance."""
    global _logger
    _logger = None
