"""
Structured logging for reconx framework.
"""
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from rich.logging import RichHandler
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
        
        # Rich handler for console output
        rich_handler = RichHandler(
            console=self.console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True
        )
        rich_handler.setLevel(level)
        self.logger.addHandler(rich_handler)
        
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
    
    def _log(self, level: str, message: str, **extra):
        """Internal log method with structured formatting."""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "logger": self.name,
            "message": message,
            **self.phase_context,
            **extra
        }
        
        # Log to file as JSON if file handler exists
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler) and not isinstance(handler, RichHandler):
                handler.emit(logging.makeLogRecord({
                    'name': self.name,
                    'level': getattr(logging, level.upper()),
                    'msg': json.dumps(log_data),
                    'args': (),
                }))
        
        # Log to console via Rich
        getattr(self.logger, level.lower())(message)
    
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
        """Log tool execution start."""
        self.info(f"Starting tool: {tool}", tool=tool, command=command, event="tool_start", **extra)
    
    def tool_end(self, tool: str, output_file: Optional[str] = None, 
                 item_count: int = 0, **extra):
        """Log tool execution end."""
        self.info(f"Tool completed: {tool} ({item_count} items)", 
                  tool=tool, output_file=output_file, 
                  item_count=item_count, event="tool_end", **extra)
    
    def tool_skipped(self, tool: str, reason: str, **extra):
        """Log tool skip."""
        self.warning(f"Tool skipped: {tool} - {reason}", 
                     tool=tool, reason=reason, event="tool_skipped", **extra)
    
    def phase_start(self, phase: str, **extra):
        """Log phase start."""
        self.info(f"{'='*50}", event="phase_separator")
        self.info(f"Starting Phase: {phase}", phase=phase, event="phase_start", **extra)
    
    def phase_end(self, phase: str, output_file: str, item_count: int, **extra):
        """Log phase end."""
        self.info(f"Phase completed: {phase} ({item_count} items) -> {output_file}",
                  phase=phase, output_file=output_file, 
                  item_count=item_count, event="phase_end", **extra)
    
    def finding(self, finding_type: str, severity: str, url: str, **extra):
        """Log a finding discovery."""
        self.info(f"Finding: [{severity.upper()}] {finding_type} at {url}",
                  finding_type=finding_type, severity=severity, 
                  url=url, event="finding", **extra)


# Global logger instance
_logger: Optional[StructuredLogger] = None


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
