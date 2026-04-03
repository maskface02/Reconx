"""
Base phase class for reconx framework.
"""
from abc import ABC, abstractmethod
from typing import Any, List
from pathlib import Path

from core.workspace import Workspace
from core.logger import get_logger
from core.runner import AsyncRunner
from core.models import PhaseOutput


class PhaseException(Exception):
    """Exception raised during phase execution."""
    pass


class BasePhase(ABC):
    """Base class for all reconx phases."""
    
    name: str = "Base Phase"
    phase_number: int = 0
    input_file: str = ""
    output_file: str = ""
    
    def __init__(self, workspace: Workspace, config: dict):
        self.workspace = workspace
        self.config = config
        self.logger = get_logger()
        self.runner = AsyncRunner(
            rate_limit=config.get('rate_limit', 50),
            timeout=300  # Framework default: 300 seconds
        )
        self.tools_config = config.get('tools', {})
    
    def get_tool_path(self, tool_name: str) -> str:
        """Get the configured path for a tool."""
        return self.tools_config.get(tool_name, tool_name)
    
    def tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available."""
        tool_path = self.get_tool_path(tool_name)
        return self.runner.check_tool(tool_path)
    
    @abstractmethod
    async def run(self) -> PhaseOutput:
        """Execute the phase."""
        pass
    
    @abstractmethod
    def parse_output(self, raw: str) -> List[Any]:
        """Parse raw tool output into structured data."""
        pass
    
    def validate_output(self, output_file: Path) -> bool:
        """Validate phase output file."""
        if not output_file.exists():
            return False
        try:
            import json
            with open(output_file, 'r') as f:
                data = json.load(f)
                return isinstance(data, (list, dict))
        except (json.JSONDecodeError, IOError):
            return False
    
    def skip_if_cached(self, force: bool = False) -> bool:
        """Check if phase should be skipped due to cached output."""
        if force:
            return False
        output_path = self.workspace.get_phase_output(self.phase_number)
        return output_path.exists()
