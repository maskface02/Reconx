"""
Report generator for reconx framework.
Generates findings summaries in various formats.
"""
import json
from pathlib import path 
from datetime import datetime
from typing import List, Dict, Any
from core.workspace import Workspace
from core.models import Finding, ExploitResult


class ReportGenerator:
    """Generate reports from reconx findings."""
    
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.target = workspace.target
    
    def generate_json(self, output_path: str) -> None:
        """Generate JSON report."""
        report_data = self._collect_report_data()
        
        with open(output_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
    
    def generate_markdown(self, output_path: str) -> None:
        """Generate Markdown report."""
        data = self._collect_report_data()
        
        md = []
        md.append(f"# Reconx Report: {self.target}")
        md.append(f"\nGenerated: {datetime.now().isoformat()}\n")
        
        # Executive Summary
        md.append("## Executive Summary\n")
        md.append(f"- **Target:** {self.target}")
        md.append(f"- **Phases Completed:** {len(data.get('phases_completed', []))}/6")
        md.append(f"- **Confirmed Findings:** {data.get('summary', {}).get('confirmed', 0)}")
        md.append(f"- **Successful Exploits:** {data.get('summary', {}).get('exploits_successful', 0)}\n")
        
        # Findings by Severity
        md.append("## Findings by Severity\n")
        severity_counts = data.get('summary', {}).get('by_severity', {})
        for sev in ['critical', 'high', 'medium', 'low', 'info']:
            count = severity_counts.get(sev, 0)
            md.append(f"- **{sev.upper()}:** {count}")
        md.append("")
        
        # Findings by Type
        md.append("## Findings by Type\n")
        type_counts = data.get('summary', {}).get('by_type', {})
        for vuln_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            md.append(f"- **{vuln_type}:** {count}")
        md.append("")
        
        # Detailed Findings
        md.append("## Detailed Findings\n")
        
        for finding in data.get('confirmed_findings', []):
            md.append(f"### {finding.get('vuln_type', 'Unknown').upper()}: {finding.get('url', 'N/A')}\n")
            md.append(f"- **ID:** {finding.get('id', 'N/A')}")
            md.append(f"- **Severity:** {finding.get('severity', 'unknown')}")
            md.append(f"- **Tool:** {finding.get('tool', 'unknown')}")
            md.append(f"- **URL:** {finding.get('url', 'N/A')}")
            if finding.get('param'):
                md.append(f"- **Parameter:** {finding.get('param')}")
            md.append(f"- **Confidence:** {finding.get('confidence', 'unknown')}")
            md.append(f"- **Evidence:**\n```\n{finding.get('evidence', 'N/A')[:500]}\n```\n")
        
        # Exploit Results
        md.append("## Exploitation Results\n")
        
        for exploit in data.get('exploit_results', []):
            status = "✅ Success" if exploit.get('exploit_success') else "❌ Failed"
            md.append(f"### {exploit.get('finding_id', 'N/A')} - {status}\n")
            md.append(f"- **Tool Used:** {exploit.get('tool_used', 'N/A')}")
            md.append(f"- **Impact:** {exploit.get('impact', 'N/A')}")
            if exploit.get('output_path'):
                md.append(f"- **Output:** {exploit.get('output_path')}")
            md.append("")
        
        # Write report
        with open(output_path, 'w') as f:
            f.write('\n'.join(md))
    
    def generate_html(self, output_path: str) -> None:
        """Generate HTML report."""
        data = self._collect_report_data()
        
        html = []
        html.append("<!DOCTYPE html>")
        html.append("<html lang='en'>")
        html.append("<head>")
        html.append("  <meta charset='UTF-8'>")
        html.append("  <meta name='viewport' content='width=device-width, initial-scale=1.0'>")
        html.append(f"  <title>Reconx Report: {self.target}</title>")
        html.append("  <style>")
        html.append(self._get_css_styles())
        html.append("  </style>")
        html.append("</head>")
        html.append("<body>")
        html.append("  <div class='container'>")
        
        # Header
        html.append(f"    <h1>Reconx Report: {self.target}</h1>")
        html.append(f"    <p class='timestamp'>Generated: {datetime.now().isoformat()}</p>")
        
        # Summary
        html.append("    <div class='summary'>")
        html.append("      <h2>Executive Summary</h2>")
        html.append("      <table>")
        html.append(f"        <tr><td>Target</td><td>{self.target}</td></tr>")
        html.append(f"        <tr><td>Phases Completed</td><td>{len(data.get('phases_completed', []))}/6</td></tr>")
        html.append(f"        <tr><td>Confirmed Findings</td><td class='highlight'>{data.get('summary', {}).get('confirmed', 0)}</td></tr>")
        html.append(f"        <tr><td>Successful Exploits</td><td>{data.get('summary', {}).get('exploits_successful', 0)}</td></tr>")
        html.append("      </table>")
        html.append("    </div>")
        
        # Severity Chart
        html.append("    <div class='severity-chart'>")
        html.append("      <h2>Findings by Severity</h2>")
        severity_counts = data.get('summary', {}).get('by_severity', {})
        for sev in ['critical', 'high', 'medium', 'low', 'info']:
            count = severity_counts.get(sev, 0)
            html.append(f"      <div class='severity-bar {sev}'>{sev.upper()}: {count}</div>")
        html.append("    </div>")
        
        # Findings Table
        html.append("    <div class='findings'>")
        html.append("      <h2>Confirmed Findings</h2>")
        html.append("      <table>")
        html.append("        <thead>")
        html.append("          <tr><th>ID</th><th>Type</th><th>Severity</th><th>URL</th><th>Tool</th></tr>")
        html.append("        </thead>")
        html.append("        <tbody>")
        
        for finding in data.get('confirmed_findings', []):
            sev_class = finding.get('severity', 'info')
            html.append(f"          <tr class='{sev_class}'>")
            html.append(f"            <td>{finding.get('id', 'N/A')}</td>")
            html.append(f"            <td>{finding.get('vuln_type', 'N/A')}</td>")
            html.append(f"            <td class='severity'>{finding.get('severity', 'N/A')}</td>")
            html.append(f"            <td>{finding.get('url', 'N/A')}</td>")
            html.append(f"            <td>{finding.get('tool', 'N/A')}</td>")
            html.append("          </tr>")
        
        html.append("        </tbody>")
        html.append("      </table>")
        html.append("    </div>")
        
        # Detailed Findings
        html.append("    <div class='details'>")
        html.append("      <h2>Detailed Findings</h2>")
        
        for finding in data.get('confirmed_findings', []):
            html.append(f"      <div class='finding-card {finding.get('severity', 'info')}'>")
            html.append(f"        <h3>{finding.get('vuln_type', 'Unknown').upper()}</h3>")
            html.append(f"        <p><strong>URL:</strong> {finding.get('url', 'N/A')}</p>")
            if finding.get('param'):
                html.append(f"        <p><strong>Parameter:</strong> {finding.get('param')}</p>")
            html.append(f"        <p><strong>Severity:</strong> <span class='severity-badge {finding.get('severity', 'info')}'>{finding.get('severity', 'N/A')}</span></p>")
            html.append("        <p><strong>Evidence:</strong></p>")
            html.append(f"        <pre>{finding.get('evidence', 'N/A')[:500]}</pre>")
            html.append("      </div>")
        
        html.append("    </div>")
        
        # Footer
        html.append("    <div class='footer'>")
        html.append("      <p>Generated by reconx - Modular Penetration Testing Framework</p>")
        html.append("    </div>")
        
        html.append("  </div>")
        html.append("</body>")
        html.append("</html>")
        
        # Write report
        with open(output_path, 'w') as f:
            f.write('\n'.join(html))
    
    def _collect_report_data(self) -> Dict[str, Any]:
        """Collect all data for the report."""
        data = {
            'target': self.target,
            'timestamp': datetime.now().isoformat(),
            'phases_completed': [],
            'confirmed_findings': [],
            'exploit_results': [],
            'summary': {
                'confirmed': 0,
                'review_queue': 0,
                'dropped': 0,
                'exploits_successful': 0,
                'by_severity': {},
                'by_type': {}
            }
        }
        
        # Get workspace status
        status = self.workspace.get_status()
        data['phases_completed'] = status.get('phases_completed', [])
        
        # Load findings
        confirmed = self.workspace.load_findings("confirmed_findings.json")
        review_queue = self.workspace.load_findings("review_queue.json")
        dropped = self.workspace.load_findings("dropped_findings.json")
        
        data['confirmed_findings'] = [f.model_dump() for f in confirmed]
        data['summary']['confirmed'] = len(confirmed)
        data['summary']['review_queue'] = len(review_queue)
        data['summary']['dropped'] = len(dropped)
        
        # Calculate severity and type counts
        for finding in confirmed:
            sev = finding.severity
            vuln_type = finding.vuln_type
            
            data['summary']['by_severity'][sev] = data['summary']['by_severity'].get(sev, 0) + 1
            data['summary']['by_type'][vuln_type] = data['summary']['by_type'].get(vuln_type, 0) + 1
        
        # Load exploit results
        exploit_file = self.workspace.workspace_path / "exploit_results.json"
        if exploit_file.exists():
            with open(exploit_file, 'r') as f:
                exploit_data = json.load(f)
                data['exploit_results'] = exploit_data
                data['summary']['exploits_successful'] = sum(
                    1 for e in exploit_data if e.get('exploit_success')
                )
        
        return data
    
    def _get_css_styles(self) -> str:
        """Get CSS styles for HTML report."""
        return """
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        line-height: 1.6;
        color: #333;
        background: #f5f5f5;
        margin: 0;
        padding: 20px;
    }
    .container {
        max-width: 1200px;
        margin: 0 auto;
        background: white;
        padding: 30px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
    h2 { color: #34495e; margin-top: 30px; }
    h3 { color: #555; }
    .timestamp { color: #7f8c8d; font-style: italic; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
    th { background: #34495e; color: white; }
    tr:hover { background: #f5f5f5; }
    .severity-chart { margin: 20px 0; }
    .severity-bar { 
        padding: 10px; margin: 5px 0; color: white; font-weight: bold;
        border-radius: 4px;
    }
    .severity-bar.critical { background: #e74c3c; }
    .severity-bar.high { background: #e67e22; }
    .severity-bar.medium { background: #f39c12; }
    .severity-bar.low { background: #3498db; }
    .severity-bar.info { background: #95a5a6; }
    .finding-card {
        border: 1px solid #ddd; border-radius: 8px; padding: 20px;
        margin: 15px 0; background: #fafafa;
    }
    .finding-card.critical { border-left: 5px solid #e74c3c; }
    .finding-card.high { border-left: 5px solid #e67e22; }
    .finding-card.medium { border-left: 5px solid #f39c12; }
    .finding-card.low { border-left: 5px solid #3498db; }
    .finding-card.info { border-left: 5px solid #95a5a6; }
    .severity-badge {
        padding: 4px 12px; border-radius: 4px; color: white; font-size: 12px;
        text-transform: uppercase;
    }
    .severity-badge.critical { background: #e74c3c; }
    .severity-badge.high { background: #e67e22; }
    .severity-badge.medium { background: #f39c12; }
    .severity-badge.low { background: #3498db; }
    .severity-badge.info { background: #95a5a6; }
    pre {
        background: #2c3e50; color: #ecf0f1; padding: 15px;
        border-radius: 4px; overflow-x: auto; font-size: 13px;
    }
    .highlight { font-weight: bold; color: #e74c3c; }
    .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #7f8c8d; text-align: center; }
"""
