"""
Workspace and file management for reconx framework.
"""
import os
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from .models import Finding


class Workspace:
    """Manages the workspace directory structure for a target."""
    
    def __init__(self, target: str, base_path: str = "./workspaces"):
        self.target = target
        self.base_path = Path(base_path)
        self.workspace_path = self.base_path / target
        self.raw_path = self.workspace_path / "raw"
        self.logs_path = self.workspace_path / "logs"
        self.exploits_path = self.workspace_path / "exploits"
        self.baselines_path = self.workspace_path / "baselines"
        self.gf_patterns_path = self.workspace_path / "gf_patterns"
        
    def create(self) -> None:
        """Create the workspace directory structure."""
        for path in [self.workspace_path, self.raw_path, self.logs_path, 
                     self.exploits_path, self.baselines_path, self.gf_patterns_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def exists(self) -> bool:
        """Check if workspace exists."""
        return self.workspace_path.exists()
    
    def clear(self) -> None:
        """Clear the workspace."""
        if self.workspace_path.exists():
            shutil.rmtree(self.workspace_path)
        self.create()
    
    def get_raw_file(self, filename: str) -> Path:
        """Get path to a raw output file."""
        return self.raw_path / filename
    
    def get_log_file(self, phase: str) -> Path:
        """Get path to a phase log file."""
        return self.logs_path / f"{phase}.log"
    
    def get_phase_output(self, phase: int or str) -> Path:
        """Get path to a phase output JSON file."""
        if isinstance(phase, int):
            return self.workspace_path / f"phase{phase}_output.json"
        return self.workspace_path / f"{phase}_output.json"
    
    def save_phase_output(self, phase: int or str, data: Any) -> None:
        """Save phase output to JSON file."""
        output_file = self.get_phase_output(phase)
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def load_phase_output(self, phase: int or str) -> Optional[Any]:
        """Load phase output from JSON file."""
        output_file = self.get_phase_output(phase)
        if output_file.exists():
            with open(output_file, 'r') as f:
                return json.load(f)
        return None
    
    def phase_completed(self, phase: int or str) -> bool:
        """Check if a phase has completed (output file exists)."""
        return self.get_phase_output(phase).exists()
    
    def save_findings(self, findings: List[Finding], filename: str) -> None:
        """Save findings to a JSON file."""
        output_file = self.workspace_path / filename
        with open(output_file, 'w') as f:
            json.dump([f.model_dump() for f in findings], f, indent=2)
    
    def load_findings(self, filename: str) -> List[Finding]:
        """Load findings from a JSON file."""
        input_file = self.workspace_path / filename
        if not input_file.exists():
            return []
        with open(input_file, 'r') as f:
            data = json.load(f)
            return [Finding(**item) for item in data]
    
    def review_queue_size(self) -> int:
        """Get the number of findings in the review queue."""
        review_file = self.workspace_path / "review_queue.json"
        if review_file.exists():
            with open(review_file, 'r') as f:
                data = json.load(f)
                return len(data)
        return 0
    
    def save_text_file(self, filename: str, lines: List[str]) -> Path:
        """Save lines to a text file."""
        filepath = self.workspace_path / filename
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))
        return filepath
    
    def load_text_file(self, filename: str) -> List[str]:
        """Load lines from a text file."""
        filepath = self.workspace_path / filename
        if not filepath.exists():
            return []
        with open(filepath, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    
    def save_baseline(self, url: str, baseline: Dict[str, Any]) -> None:
        """Save a baseline response for a URL."""
        safe_url = url.replace('://', '_').replace('/', '_').replace(':', '_')
        baseline_file = self.baselines_path / f"{safe_url}.json"
        with open(baseline_file, 'w') as f:
            json.dump(baseline, f, indent=2)
    
    def load_baseline(self, url: str) -> Optional[Dict[str, Any]]:
        """Load a baseline response for a URL."""
        safe_url = url.replace('://', '_').replace('/', '_').replace(':', '_')
        baseline_file = self.baselines_path / f"{safe_url}.json"
        if baseline_file.exists():
            with open(baseline_file, 'r') as f:
                return json.load(f)
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get workspace status summary."""
        status = {
            "target": self.target,
            "workspace_path": str(self.workspace_path),
            "phases_completed": [],
            "findings": {
                "confirmed": 0,
                "review_queue": 0,
                "dropped": 0,
                "exploits": 0
            }
        }
        
        for phase in [1, 2, 3, 4, 5, 6]:
            if self.phase_completed(phase):
                status["phases_completed"].append(phase)
        
        # Count findings
        for finding_type in ["confirmed_findings", "review_queue", "dropped_findings"]:
            findings = self.load_findings(f"{finding_type}.json")
            status["findings"][finding_type.replace("_findings", "") if "confirmed" in finding_type else finding_type.replace("_", "_")] = len(findings)
        
        # Count exploit results
        exploit_file = self.workspace_path / "exploit_results.json"
        if exploit_file.exists():
            with open(exploit_file, 'r') as f:
                exploits = json.load(f)
                status["findings"]["exploits"] = len(exploits)
        
        return status
