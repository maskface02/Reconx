"""
False Positive Filter Module
Confidence-based scoring engine to filter findings.
"""
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from core.workspace import Workspace
from core.models import Finding, PhaseOutput
from core.utils import differs_from_baseline, is_generic_template
from core.logger import get_logger


# Scoring signals and weights
SIGNALS = {
    # Evidence quality (positive)
    "response_diff_confirmed": 30,   # response clearly differs from baseline
    "nuclei_matcher_positive": 25,   # nuclei matched a specific pattern/regex
    "multiple_tools_agree": 20,      # same url+param flagged by 2+ tools
    "cve_version_match": 20,         # known CVE with version fingerprint match
    
    # Noise indicators (negative)
    "waf_detected": -15,             # WAF may have intercepted/altered response
    "generic_template": -10,         # template tagged as noisy/low-signal
    "timing_based_only": -20,        # finding relies purely on response time
    "single_tool_no_evidence": -15,  # only one tool, no response evidence
    "identical_responses": -25,      # all requests return same body (WAF block page)
}


class FPFilter:
    """False Positive Filter with confidence scoring."""
    
    name = "False Positive Filter"
    phase_key = "fp"
    
    def __init__(self, workspace: Workspace, config: dict):
        self.workspace = workspace
        self.config = config
        self.logger = get_logger()
        self.baseline_responses: Dict[str, Any] = {}
        self.waf_detected_urls: set = set()
    
    async def run(self) -> PhaseOutput:
        """Run the false positive filter on Phase 5 findings."""
        self.logger.phase_start(self.name)
        
        # Load findings from Phase 5
        findings = self.workspace.load_findings("phase5_output.json")
        
        if not findings:
            self.logger.info("No findings to filter")
            return PhaseOutput(
                phase=self.name,
                count=0,
                output_file=str(self.workspace.get_phase_output("fp"))
            )
        
        self.logger.info(f"Filtering {len(findings)} findings")
        
        # Load baseline responses
        await self._load_baselines()
        
        # Load WAF detection info
        self._load_waf_info()
        
        # Score and categorize findings
        confirmed = []
        review_queue = []
        dropped = []
        
        for finding in findings:
            score, breakdown = self._score_finding(finding)
            finding.score = score
            finding.score_breakdown = breakdown
            finding.confidence = self._assign_confidence(score)
            
            # Route based on confidence
            if finding.confidence == "high":
                finding.confirmed = True
                confirmed.append(finding)
            elif finding.confidence == "medium":
                review_queue.append(finding)
            else:
                dropped.append(finding)
        
        # Save categorized findings
        self.workspace.save_findings(confirmed, "confirmed_findings.json")
        self.workspace.save_findings(review_queue, "review_queue.json")
        self.workspace.save_findings(dropped, "dropped_findings.json")
        
        self.logger.info(
            f"Filter complete: {len(confirmed)} confirmed, "
            f"{len(review_queue)} for review, {len(dropped)} dropped"
        )
        
        self.logger.phase_end(
            self.name, 
            str(self.workspace.workspace_path / "confirmed_findings.json"),
            len(confirmed)
        )
        
        return PhaseOutput(
            phase=self.name,
            count=len(confirmed),
            output_file=str(self.workspace.workspace_path / "confirmed_findings.json"),
            metadata={
                "confirmed": len(confirmed),
                "review_queue": len(review_queue),
                "dropped": len(dropped)
            }
        )
    
    async def _load_baselines(self) -> None:
        """Load baseline responses for comparison."""
        # Check if baselines exist
        if not self.workspace.baselines_path.exists():
            self.logger.warning("No baseline responses found")
            return
        
        for baseline_file in self.workspace.baselines_path.glob("*.json"):
            try:
                with open(baseline_file, 'r') as f:
                    data = json.load(f)
                    self.baseline_responses[data.get('url', '')] = data
            except json.JSONDecodeError:
                continue
        
        self.logger.info(f"Loaded {len(self.baseline_responses)} baseline responses")
    
    def _load_waf_info(self) -> None:
        """Load WAF detection information from Phase 2."""
        phase2_data = self.workspace.load_phase_output(2)
        if phase2_data:
            for probe in phase2_data:
                if probe.get('waf_bypass_needed') or probe.get('waf'):
                    self.waf_detected_urls.add(probe.get('url', ''))
    
    def _score_finding(self, finding: Finding) -> tuple[int, Dict[str, Any]]:
        """Score a finding based on signals."""
        score = 0
        breakdown = {}
        
        # Check response diff vs baseline
        if finding.response_snippet:
            baseline = self.baseline_responses.get(finding.url)
            if differs_from_baseline(finding.url, finding.response_snippet, baseline):
                score += SIGNALS["response_diff_confirmed"]
                breakdown["response_diff_confirmed"] = True
        
        # Check if nuclei had a positive matcher
        if finding.tool == "nuclei" and finding.evidence and len(finding.evidence) > 20:
            score += SIGNALS["nuclei_matcher_positive"]
            breakdown["nuclei_matcher_positive"] = True
        
        # Check cross-tool agreement (would need to track all findings)
        # This is simplified - in production, compare against all findings
        if self._has_secondary_confirmation(finding):
            score += SIGNALS["multiple_tools_agree"]
            breakdown["multiple_tools_agree"] = True
        
        # CVE version match
        if finding.template and "CVE-" in finding.template:
            score += SIGNALS["cve_version_match"]
            breakdown["cve_version_match"] = True
        
        # WAF penalty
        if finding.url in self.waf_detected_urls:
            score += SIGNALS["waf_detected"]
            breakdown["waf_detected"] = True
        
        # Generic template penalty
        if is_generic_template(finding.template):
            score += SIGNALS["generic_template"]
            breakdown["generic_template"] = True
        
        # Timing-based only penalty
        if finding.vuln_type in ["sqli", "ssrf"] and not finding.response_snippet:
            score += SIGNALS["timing_based_only"]
            breakdown["timing_based_only"] = True
        
        # Single tool with no evidence penalty
        if not finding.response_snippet and finding.tool != "nuclei":
            score += SIGNALS["single_tool_no_evidence"]
            breakdown["single_tool_no_evidence"] = True
        
        return score, breakdown
    
    def _assign_confidence(self, score: int) -> str:
        """Assign confidence level based on score."""
        if score >= 50:
            return "high"
        elif score >= 20:
            return "medium"
        else:
            return "low"
    
    def _has_secondary_confirmation(self, finding: Finding) -> bool:
        """Check if finding has secondary confirmation from another tool."""
        # Load all findings and check for duplicates
        all_findings = self.workspace.load_findings("phase5_output.json")
        
        url_param_key = f"{finding.url}:{finding.param or ''}"
        
        matching_findings = [
            f for f in all_findings 
            if f.url == finding.url 
            and f.param == finding.param 
            and f.tool != finding.tool
            and f.vuln_type == finding.vuln_type
        ]
        
        return len(matching_findings) > 0
    
    def get_review_queue_size(self) -> int:
        """Get the number of findings in the review queue."""
        return self.workspace.review_queue_size()
