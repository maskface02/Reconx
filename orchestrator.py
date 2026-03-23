"""
Pipeline orchestrator for reconx framework.
Manages phase execution and chaining.
"""
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

from core.workspace import Workspace
from core.logger import get_logger, reset_logger
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
        # Determine phases to run
        if single_phase is not None:
            phases = [single_phase]
        else:
            phases = [1, 2, 3, 4, 5, "fp", 6]
            if to_phase:
                phases = [p for p in phases if (isinstance(p, int) and p <= to_phase) or p == "fp"]
        
        self.logger.info(
            f"Starting pipeline for {self.target}",
            phases=phases,
            force=self.force
        )
        
        for phase_key in phases:
            # Skip phases before from_phase
            if isinstance(phase_key, int) and phase_key < from_phase:
                self.logger.info(f"Skipping Phase {phase_key} (before --from-phase)")
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
            
            # Run phase
            self.logger.set_phase_context(
                phase=str(phase_key),
                target=self.target
            )
            
            try:
                phase = PhaseClass(self.workspace, self.config)
                output = await phase.run()
                
                self.logger.info(
                    f"Phase {phase_key} complete",
                    output_file=output.output_file,
                    count=output.count
                )
                
            except PhaseException as e:
                self.logger.error(f"Phase {phase_key} failed: {e}")
                return False
            except Exception as e:
                self.logger.error(f"Unexpected error in Phase {phase_key}: {e}")
                import traceback
                self.logger.debug(traceback.format_exc())
                return False
            
            # Special handling for FP filter phase
            if phase_key == "fp":
                review_size = self.workspace.review_queue_size()
                if review_size > 0:
                    self.logger.warning(
                        f"{review_size} findings need manual review."
                    )
                    self.logger.warning(
                        f"Run: reconx review --target {self.target} "
                        f"then re-run from phase 6."
                    )
                    return True  # Not a failure, just needs review
        
        self.logger.info("Pipeline completed successfully")
        return True
    
    async def run_phase(self, phase_number: int) -> bool:
        """Run a single phase."""
        return await self.run_pipeline(single_phase=phase_number)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current workspace status."""
        return self.workspace.get_status()


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
