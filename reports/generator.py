"""
Report generator for reconx framework.
Generates findings summaries and per-phase reports in various formats.
"""
import json
import html as html_mod
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
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

    # ─── Per-Phase Reports ──────────────────────────────────────────────

    PHASE_NAMES = {
        1: "Subdomain & Asset Discovery",
        2: "HTTP Probing & Tech Fingerprinting",
        3: "URL & Endpoint Crawling",
        4: "Directory Enumeration & Parameter Discovery",
        5: "Vulnerability Scanning & Secret Hunting",
        6: "Targeted Exploitation",
    }

    def generate_phase_html(self, phase: int, output_path: str) -> None:
        """Generate an interactive HTML report for a specific phase."""
        data = self._load_phase_data(phase)
        if data is None:
            return

        title = self.PHASE_NAMES.get(phase, f"Phase {phase}")
        count = len(data) if isinstance(data, list) else 0

        css = self._get_phase_css()
        body = self._render_phase_html(phase, data, count)

        html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ReconX — {self.target} — {title}</title>
<style>{css}</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>🔍 ReconX Report</h1>
<p class="target">Target: <strong>{html_mod.escape(self.target)}</strong></p>
<p class="phase">Phase {phase}: {html_mod.escape(title)}</p>
<p class="meta">{count} items &middot; {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
</div>
<input type="text" id="search" placeholder="🔎  Filter results..." onkeyup="filterTable()">
{body}
<div class="footer">Generated by <strong>reconx</strong> — <a href="https://github.com/maskface02/reconx">github.com/maskface02/reconx</a></div>
</div>
<script>
function filterTable() {{
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('#results tbody tr').forEach(row => {{
    row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""
        with open(output_path, 'w') as f:
            f.write(html_out)

    def generate_phase_markdown(self, phase: int, output_path: str) -> None:
        """Generate a Markdown report for a specific phase."""
        data = self._load_phase_data(phase)
        if data is None:
            return

        title = self.PHASE_NAMES.get(phase, f"Phase {phase}")
        count = len(data) if isinstance(data, list) else 0

        md = [
            f"# ReconX — {self.target}",
            f"",
            f"**Phase {phase}: {title}** — {count} items",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"",
            "---",
            "",
        ]

        md.extend(self._render_phase_md(phase, data))

        with open(output_path, 'w') as f:
            f.write('\n'.join(md))

    def _load_phase_data(self, phase: int) -> Optional[Any]:
        """Load phase output JSON data."""
        return self.workspace.load_phase_output(phase)

    def _render_phase_html(self, phase: int, data: Any, count: int) -> str:
        """Render phase-specific HTML body."""
        if phase == 1:
            return self._html_phase1(data, count)
        elif phase == 2:
            return self._html_phase2(data, count)
        elif phase == 3:
            return self._html_phase3(data, count)
        elif phase == 4:
            return self._html_phase4(data, count)
        elif phase == 5:
            return self._html_phase5(data, count)
        elif phase == 6:
            return self._html_phase6(data, count)
        return f"<p>No report available for Phase {phase}</p>"

    def _render_phase_md(self, phase: int, data: Any) -> List[str]:
        """Render phase-specific Markdown body."""
        if phase == 1:
            return self._md_phase1(data)
        elif phase == 2:
            return self._md_phase2(data)
        elif phase == 3:
            return self._md_phase3(data)
        elif phase == 4:
            return self._md_phase4(data)
        elif phase == 5:
            return self._md_phase5(data)
        elif phase == 6:
            return self._md_phase6(data)
        return [f"No report available for Phase {phase}"]

    # ─── Phase 1: Subdomains ────────────────────────────────────────────

    def _html_phase1(self, data, count):
        rows = ""
        for item in data:
            sub = html_mod.escape(item.get('subdomain', ''))
            ip = html_mod.escape(item.get('ip') or '')
            cname = html_mod.escape(item.get('cname') or '—')
            asn = html_mod.escape(item.get('asn') or '—')
            sources = html_mod.escape(', '.join(item.get('sources', [])) or '—')
            alive = '✅' if item.get('alive') else '❌'
            
            # Make subdomain clickable
            sub_display = f'<a href="https://{sub}" target="_blank" rel="noopener noreferrer">{sub}</a>' if sub and sub != '—' else sub
            
            # Make IP clickable
            if ip and ip != '—':
                ip_display = f'<a href="https://ipinfo.io/{ip}" target="_blank" rel="noopener noreferrer">{ip}</a>'
            else:
                ip_display = '—'
            
            rows += f"<tr><td>{sub_display}</td><td>{ip_display}</td><td>{cname}</td><td>{asn}</td><td>{sources}</td><td>{alive}</td></tr>\n"

        return f"""<table id="results"><thead><tr>
<th>Subdomain</th><th>IP</th><th>CNAME</th><th>ASN</th><th>Sources</th><th>Alive</th>
</tr></thead><tbody>{rows}</tbody></table>"""

    def _md_phase1(self, data):
        md = ["## Subdomains\n", "| Subdomain | IP | CNAME | ASN | Sources | Alive |", "|---|---|---|---|---|---|"]
        for item in data:
            sub = item.get('subdomain', '')
            ip = item.get('ip') or '—'
            cname = item.get('cname') or '—'
            asn = item.get('asn') or '—'
            sources = ', '.join(item.get('sources', [])) or '—'
            alive = '✅' if item.get('alive') else '❌'
            md.append(f"| {sub} | {ip} | {cname} | {asn} | {sources} | {alive} |")
        return md

    # ─── Phase 2: HTTP Probes ───────────────────────────────────────────

    def _html_phase2(self, data, count):
        rows = ""
        for item in data:
            url = html_mod.escape(item.get('url', ''))
            sc = item.get('status_code', 0)
            color = {200: '#27ae60', 301: '#f39c12', 302: '#f39c12', 403: '#e74c3c', 404: '#95a5a6', 500: '#e74c3c'}.get(sc, '#7f8c8d')
            title = html_mod.escape(item.get('title') or '—')
            tech = html_mod.escape(', '.join(item.get('tech', [])) or '—')
            waf = html_mod.escape(item.get('waf') or '—')
            ports = ', '.join(str(p) for p in item.get('ports', [])) or '—'
            rows += f'<tr><td><a href="{url}" target="_blank">{url}</a></td><td style="color:{color};font-weight:bold">{sc}</td><td>{title}</td><td>{tech}</td><td>{waf}</td><td>{ports}</td></tr>\n'

        return f"""<table id="results"><thead><tr>
<th>URL</th><th>Status</th><th>Title</th><th>Tech Stack</th><th>WAF</th><th>Ports</th>
</tr></thead><tbody>{rows}</tbody></table>"""

    def _md_phase2(self, data):
        md = ["## HTTP Probes\n", "| URL | Status | Title | Tech | WAF | Ports |", "|---|---|---|---|---|---|"]
        for item in data:
            md.append(f"| {item.get('url','')} | {item.get('status_code',0)} | {item.get('title','—')} | {', '.join(item.get('tech',[])) or '—'} | {item.get('waf') or '—'} | {', '.join(str(p) for p in item.get('ports',[])) or '—'} |")
        return md

    # ─── Phase 3: Crawled URLs ──────────────────────────────────────────

    def _html_phase3(self, data, count):
        rows = ""
        for item in data:
            url = html_mod.escape(item.get('url', ''))
            source = html_mod.escape(item.get('source', ''))
            method = html_mod.escape(item.get('method', 'GET'))
            params = html_mod.escape(', '.join(item.get('params', [])) or '—')
            rows += f"<tr><td><a href=\"{url}\" target=\"_blank\">{url}</a></td><td>{source}</td><td>{method}</td><td>{params}</td></tr>\n"

        return f"""<table id="results"><thead><tr>
<th>URL</th><th>Source</th><th>Method</th><th>Parameters</th>
</tr></thead><tbody>{rows}</tbody></table>"""

    def _md_phase3(self, data):
        md = ["## Crawled URLs\n", "| URL | Source | Method | Parameters |", "|---|---|---|---|"]
        for item in data:
            md.append(f"| {item.get('url','')} | {item.get('source','')} | {item.get('method','GET')} | {', '.join(item.get('params',[])) or '—'} |")
        return md

    # ─── Phase 4: Parameters ────────────────────────────────────────────

    def _html_phase4(self, data, count):
        rows = ""
        for item in data:
            url = html_mod.escape(item.get('url', ''))
            url_display = f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>' if url else url
            param = html_mod.escape(item.get('param', ''))
            method = html_mod.escape(item.get('method', ''))
            pattern = html_mod.escape(item.get('pattern') or '—')
            rows += f"<tr><td>{url_display}</td><td>{param}</td><td>{method}</td><td>{pattern}</td></tr>\n"

        return f"""<table id="results"><thead><tr>
<th>URL</th><th>Parameter</th><th>Method</th><th>GF Pattern</th>
</tr></thead><tbody>{rows}</tbody></table>"""

    def _md_phase4(self, data):
        md = ["## Discovered Parameters\n", "| URL | Parameter | Method | GF Pattern |", "|---|---|---|---|"]
        for item in data:
            md.append(f"| {item.get('url','')} | {item.get('param','')} | {item.get('method','')} | {item.get('pattern') or '—'} |")
        return md

    # ─── Phase 5: Findings ──────────────────────────────────────────────

    def _html_phase5(self, data, count):
        sev_colors = {'critical': '#e74c3c', 'high': '#e67e22', 'medium': '#f39c12', 'low': '#3498db', 'info': '#95a5a6'}
        rows = ""
        for item in data:
            sev = item.get('severity', 'info')
            color = sev_colors.get(sev, '#7f8c8d')
            vuln = html_mod.escape(item.get('vuln_type', ''))
            url = html_mod.escape(item.get('url', ''))
            url_display = f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>' if url else url
            tool = html_mod.escape(item.get('tool', ''))
            evidence = html_mod.escape(str(item.get('evidence', ''))[:200])
            score = item.get('score', 0)
            rows += f'<tr style="border-left:4px solid {color}"><td><span style="color:{color};font-weight:bold">{sev.upper()}</span></td><td>{vuln}</td><td>{url_display}</td><td>{tool}</td><td>{score}</td><td title="{evidence}">{evidence[:100]}...</td></tr>\n'

        return f"""<table id="results"><thead><tr>
<th>Severity</th><th>Type</th><th>URL</th><th>Tool</th><th>Score</th><th>Evidence</th>
</tr></thead><tbody>{rows}</tbody></table>"""

    def _md_phase5(self, data):
        md = ["## Findings\n", "| Severity | Type | URL | Tool | Score | Evidence |", "|---|---|---|---|---|---|"]
        for item in data:
            md.append(f"| {item.get('severity','')} | {item.get('vuln_type','')} | {item.get('url','')} | {item.get('tool','')} | {item.get('score',0)} | {str(item.get('evidence',''))[:100]} |")
        return md

    # ─── Phase 6: Exploitation ──────────────────────────────────────────

    def _html_phase6(self, data, count):
        rows = ""
        for item in data:
            status = '✅' if item.get('exploit_success') else '❌'
            tool = html_mod.escape(item.get('tool_used', ''))
            finding = html_mod.escape(item.get('finding_id', ''))
            impact = html_mod.escape(item.get('impact') or '—')
            rows += f"<tr><td>{status}</td><td>{tool}</td><td>{finding}</td><td>{impact}</td></tr>\n"

        return f"""<table id="results"><thead><tr>
<th>Status</th><th>Tool</th><th>Finding ID</th><th>Impact</th>
</tr></thead><tbody>{rows}</tbody></table>"""

    def _md_phase6(self, data):
        md = ["## Exploitation Results\n", "| Status | Tool | Finding ID | Impact |", "|---|---|---|---|"]
        for item in data:
            status = '✅' if item.get('exploit_success') else '❌'
            md.append(f"| {status} | {item.get('tool_used','')} | {item.get('finding_id','')} | {item.get('impact') or '—'} |")
        return md

    # ─── Phase CSS ──────────────────────────────────────────────────────

    def _get_phase_css(self):
        return """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
.container { max-width: 1400px; margin: 0 auto; }
.header { padding: 30px 0; border-bottom: 1px solid #21262d; margin-bottom: 20px; }
.header h1 { color: #58a6ff; font-size: 28px; margin-bottom: 8px; }
.target { color: #8b949e; font-size: 16px; }
.target strong { color: #f0f6fc; }
.phase { color: #3fb950; font-size: 20px; margin: 8px 0; font-weight: 600; }
.meta { color: #8b949e; font-size: 13px; }
#search { width: 100%; padding: 12px 16px; font-size: 15px; border: 1px solid #30363d; border-radius: 6px; background: #161b22; color: #c9d1d9; margin-bottom: 16px; outline: none; }
#search:focus { border-color: #58a6ff; box-shadow: 0 0 0 3px rgba(88,166,255,0.15); }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
thead th { background: #161b22; color: #8b949e; font-weight: 600; text-align: left; padding: 12px 16px; border-bottom: 2px solid #30363d; position: sticky; top: 0; }
tbody td { padding: 10px 16px; border-bottom: 1px solid #21262d; vertical-align: top; }
tbody tr:hover { background: #161b22; }
tbody a { color: #58a6ff; text-decoration: none; }
tbody a:hover { text-decoration: underline; }
.footer { margin-top: 30px; padding: 20px 0; border-top: 1px solid #21262d; text-align: center; color: #8b949e; font-size: 13px; }
.footer a { color: #58a6ff; text-decoration: none; }
"""

    # ─── Data Table ─────────────────────────────────────────────────────

    def _render_table(self, phase, data):
        """Render data table."""
        rows = []
        for item in data:
            sub = html_mod.escape(item.get('subdomain', item.get('url', '')))
            ip = html_mod.escape(item.get('ip') or '—')
            asn_raw = item.get('asn') or ''
            cname = html_mod.escape(item.get('cname') or '—')
            sources = item.get('sources', [])
            if isinstance(sources, list):
                src_html = ''.join(f'<span>{html_mod.escape(s)}</span>' for s in sources[:3])
            else:
                src_html = html_mod.escape(str(sources)[:50])
            color, cls, label = self._get_provider_color(asn_raw)
            asn_display = html_mod.escape(label)
            rows.append(f'<tr><td class="subdomain">{sub}</td><td class="ip">{ip}</td><td><span class="badge badge-{cls}">{asn_display}</span></td><td style="font-size:12px;color:#8b949e;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{cname}</td><td class="sources">{src_html}</td></tr>')

        count = len(data)
        title = self.PHASE_NAMES.get(phase, f"Phase {phase}")

        table = f'''<div class="table-section">
<h2>{title} <span>{count} subdomains</span></h2>
<table><thead><tr><th>Subdomain</th><th>IP</th><th>ASN</th><th>CNAME</th><th>Sources</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
</div>'''
        return table
