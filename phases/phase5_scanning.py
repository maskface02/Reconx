"""
Phase 5: Secret Hunting & Vulnerability Scanning
Find leaked credentials and scan for known vulnerabilities.
"""
import json
import asyncio
from typing import List, Any, Dict
from pathlib import Path

from core.workspace import Workspace
from core.models import Finding, SecretType, PhaseOutput
from core.utils import redact_secrets
from .base import BasePhase


class Phase5Scanning(BasePhase):
    """Phase 5: Secret hunting and vulnerability scanning."""
    
    name = "Secret Hunting & Vulnerability Scanning"
    phase_number = 5
    input_file = "phase4_output.json"
    output_file = "phase5_output.json"
    
    def __init__(self, workspace: Workspace, config: dict):
        super().__init__(workspace, config)
        self.target = config['target']
        self.nuclei_templates = config.get('nuclei_templates', '/usr/share/nuclei-templates/')
        self.rate_limit = config.get('rate_limit', 50)
    
    async def run(self) -> PhaseOutput:
        """Execute Phase 5: Scanning."""
        self.logger.phase_start(self.name, target=self.target)
        
        # Load URLs
        urls = self.workspace.load_text_file("urls.txt")
        all_urls = self.workspace.load_text_file("all_urls.txt")
        js_files = self.workspace.load_text_file("js_files.txt")
        
        if not urls and not all_urls:
            self.logger.warning("No URLs found for scanning")
            return PhaseOutput(
                phase=self.name,
                count=0,
                output_file=str(self.workspace.get_phase_output(5))
            )
        
        # Run 5a and 5b in parallel
        secrets_task = self._hunt_secrets(js_files)
        vulns_task = self._scan_vulnerabilities(urls or all_urls)
        
        secrets, vulns = await asyncio.gather(secrets_task, vulns_task)
        
        # Combine findings
        all_findings = secrets + vulns
        
        self.logger.info(f"Found {len(secrets)} secrets and {len(vulns)} vulnerabilities")
        
        # Save output
        output_data = [f.model_dump() for f in all_findings]
        self.workspace.save_phase_output(5, output_data)
        
        self.logger.phase_end(self.name, str(self.workspace.get_phase_output(5)), len(all_findings))
        
        return PhaseOutput(
            phase=self.name,
            count=len(all_findings),
            output_file=str(self.workspace.get_phase_output(5)),
            metadata={"secrets": len(secrets), "vulnerabilities": len(vulns)}
        )
    
    async def _hunt_secrets(self, js_files: List[str]) -> List[Finding]:
        """5a: Hunt for secrets in JS files and other sources."""
        all_secrets = []
        
        # SecretFinder on JS files
        if js_files and self.tool_available('secretfinder'):
            for js_url in js_files[:30]:  # Limit to avoid overwhelming
                secrets = await self._run_secretfinder(js_url)
                all_secrets.extend(secrets)
        else:
            self.logger.tool_skipped('secretfinder', 'not installed or no JS files')
        
        # TruffleHog on workspace
        if self.tool_available('trufflehog'):
            secrets = await self._run_trufflehog()
            all_secrets.extend(secrets)
        else:
            self.logger.tool_skipped('trufflehog', 'not installed')
        
        # GitDorker if GitHub token configured
        if self.tool_available('gitdorker') and self.config.get('github_token'):
            secrets = await self._run_gitdorker()
            all_secrets.extend(secrets)
        else:
            self.logger.tool_skipped('gitdorker', 'not installed or no GitHub token')
        
        return all_secrets
    
    async def _run_secretfinder(self, js_url: str) -> List[Finding]:
        """Run SecretFinder on a JS file."""
        cmd = [
            self.get_tool_path('secretfinder'),
            '-i', js_url,
            '-o', 'cli'
        ]
        
        result = await self.runner.run(f'secretfinder_{js_url}', cmd)
        
        secrets = []
        if result.success:
            lines = result.stdout.split('\n')
            for line in lines:
                line = line.strip()
                if line and ':' in line:
                    parts = line.split(':', 1)
                    secret_type = parts[0].strip()
                    secret_value = parts[1].strip() if len(parts) > 1 else ''
                    
                    secrets.append(Finding(
                        url=js_url,
                        vuln_type="secret",
                        tool="secretfinder",
                        severity="high" if any(k in secret_type.lower() for k in ['key', 'token', 'secret']) else "medium",
                        evidence=redact_secrets(f"{secret_type}: {secret_value}"),
                        confidence="medium"
                    ))
        
        return secrets
    
    async def _run_trufflehog(self) -> List[Finding]:
        """Run TruffleHog on workspace files."""
        output_file = self.workspace.get_raw_file("trufflehog_out.json")
        
        cmd = [
            self.get_tool_path('trufflehog'),
            'filesystem',
            str(self.workspace.workspace_path),
            '--json',
            '-o', str(output_file)
        ]
        
        result = await self.runner.run('trufflehog', cmd, output_file)
        
        secrets = []
        if result.success and output_file.exists():
            with open(output_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            secrets.append(Finding(
                                url=data.get('SourceMetadata', {}).get('Data', {}).get('Filesystem', {}).get('file', 'unknown'),
                                vuln_type="secret",
                                tool="trufflehog",
                                severity="high",
                                evidence=redact_secrets(data.get('Raw', '')),
                                confidence="high"
                            ))
                        except json.JSONDecodeError:
                            continue
        
        return secrets
    
    async def _run_gitdorker(self) -> List[Finding]:
        """Run GitDorker for GitHub secrets."""
        output_file = self.workspace.get_raw_file("gitdorker_out.txt")
        
        cmd = [
            self.get_tool_path('gitdorker'),
            '-q', self.target,
            '-t', self.config.get('github_token', '')
        ]
        
        result = await self.runner.run('gitdorker', cmd, output_file)
        
        secrets = []
        if result.success and output_file.exists():
            with open(output_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and 'github.com' in line:
                        secrets.append(Finding(
                            url=line,
                            vuln_type="secret",
                            tool="gitdorker",
                            severity="medium",
                            evidence="Potential sensitive file exposed on GitHub",
                            confidence="low"
                        ))
        
        return secrets
    
    async def _scan_vulnerabilities(self, urls: List[str]) -> List[Finding]:
        """5b: Scan for vulnerabilities using various tools."""
        all_vulns = []
        
        # Save URLs for scanning
        urls_file = self.workspace.workspace_path / "urls_for_scanning.txt"
        with open(urls_file, 'w') as f:
            f.write('\n'.join(urls))
        
        # Nuclei scanning
        if self.tool_available('nuclei'):
            vulns = await self._run_nuclei(urls_file)
            all_vulns.extend(vulns)
        else:
            self.logger.tool_skipped('nuclei', 'not installed')
        
        # Nuclei exposures
        if self.tool_available('nuclei'):
            vulns = await self._run_nuclei_exposures(urls_file)
            all_vulns.extend(vulns)
        
        # Nikto scanning
        if self.tool_available('nikto'):
            base_urls = list(set([url.split('/')[0] + '//' + url.split('/')[2] for url in urls if '://' in url]))
            for url in base_urls[:5]:  # Limit
                vulns = await self._run_nikto(url)
                all_vulns.extend(vulns)
        else:
            self.logger.tool_skipped('nikto', 'not installed')
        
        return all_vulns
    
    async def _run_nuclei(self, urls_file: Path) -> List[Finding]:
        """Run Nuclei vulnerability scanner."""
        output_file = self.workspace.get_raw_file("nuclei_out.jsonl")
        
        cmd = [
            self.get_tool_path('nuclei'),
            '-l', str(urls_file),
            '-t', self.nuclei_templates,
            '-severity', 'critical,high,medium',
            '-json',
            '-o', str(output_file),
            '-rate-limit', str(self.rate_limit)
        ]
        
        result = await self.runner.run('nuclei', cmd, output_file)
        
        vulns = []
        if result.success and output_file.exists():
            with open(output_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            vulns.append(self._parse_nuclei_finding(data))
                        except json.JSONDecodeError:
                            continue
        
        self.logger.tool_end('nuclei', str(output_file), len(vulns))
        return vulns
    
    async def _run_nuclei_exposures(self, urls_file: Path) -> List[Finding]:
        """Run Nuclei exposure templates."""
        output_file = self.workspace.get_raw_file("nuclei_exposures.jsonl")
        exposures_path = Path(self.nuclei_templates) / "exposures"
        
        if not exposures_path.exists():
            return []
        
        cmd = [
            self.get_tool_path('nuclei'),
            '-l', str(urls_file),
            '-t', str(exposures_path),
            '-json',
            '-o', str(output_file)
        ]
        
        result = await self.runner.run('nuclei_exposures', cmd, output_file)
        
        vulns = []
        if result.success and output_file.exists():
            with open(output_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            vulns.append(self._parse_nuclei_finding(data))
                        except json.JSONDecodeError:
                            continue
        
        self.logger.tool_end('nuclei_exposures', str(output_file), len(vulns))
        return vulns
    
    async def _run_nikto(self, url: str) -> List[Finding]:
        """Run Nikto vulnerability scanner."""
        output_file = self.workspace.get_raw_file(f"nikto_{url.replace('://', '_').replace('/', '_')}.json")
        
        cmd = [
            self.get_tool_path('nikto'),
            '-h', url,
            '-Format', 'json',
            '-o', str(output_file)
        ]
        
        result = await self.runner.run(f'nikto_{url}', cmd, output_file)
        
        vulns = []
        if result.success and output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    data = json.load(f)
                    for vuln in data.get('vulnerabilities', []):
                        vulns.append(Finding(
                            url=url,
                            vuln_type=self._classify_nikto_vuln(vuln.get('msg', '')),
                            tool="nikto",
                            severity=self._nikto_severity(vuln.get('severity', '0')),
                            evidence=vuln.get('msg', ''),
                            confidence="medium"
                        ))
            except json.JSONDecodeError:
                pass
        
        return vulns
    
    def _parse_nuclei_finding(self, data: Dict) -> Finding:
        """Parse a Nuclei finding into a Finding object."""
        severity = data.get('info', {}).get('severity', 'info').lower()
        template = data.get('template-id', '')
        
        # Classify vulnerability type
        vuln_type = self._classify_nuclei_template(template, data.get('info', {}).get('name', ''))
        
        return Finding(
            url=data.get('host', ''),
            param=data.get('matched-at', ''),
            vuln_type=vuln_type,
            tool="nuclei",
            template=template,
            severity=severity,
            evidence=data.get('extracted-results', [data.get('response', '')])[0] if data.get('extracted-results') else data.get('matcher-name', ''),
            request=data.get('request', ''),
            response_snippet=data.get('response', '')[:500],
            confidence="medium"
        )
    
    def _classify_nuclei_template(self, template: str, name: str) -> str:
        """Classify nuclei template to vuln_type."""
        template_lower = template.lower()
        name_lower = name.lower()
        
        if 'sqli' in template_lower or 'sql' in name_lower:
            return "sqli"
        elif 'xss' in template_lower or 'cross-site' in name_lower:
            return "xss"
        elif 'ssrf' in template_lower:
            return "ssrf"
        elif 'xxe' in template_lower:
            return "xxe"
        elif 'lfi' in template_lower or 'file-inclusion' in name_lower:
            return "lfi"
        elif 'idor' in template_lower:
            return "idor"
        elif 'cve' in template_lower:
            return "cve"
        elif 'misconfig' in template_lower:
            return "misconfiguration"
        else:
            return "misconfiguration"
    
    def _classify_nikto_vuln(self, msg: str) -> str:
        """Classify Nikto message to vuln_type."""
        msg_lower = msg.lower()
        
        if 'xss' in msg_lower or 'cross-site' in msg_lower:
            return "xss"
        elif 'sql' in msg_lower:
            return "sqli"
        elif 'directory' in msg_lower or 'indexing' in msg_lower:
            return "misconfiguration"
        elif 'version' in msg_lower:
            return "misconfiguration"
        else:
            return "misconfiguration"
    
    def _nikto_severity(self, severity: str) -> str:
        """Convert Nikto severity to standard severity."""
        mapping = {
            '0': 'info',
            '1': 'low',
            '2': 'medium',
            '3': 'high',
            '4': 'critical'
        }
        return mapping.get(severity, 'info')
    
    def parse_output(self, raw: str) -> List[Any]:
        """Parse raw output into Finding objects."""
        data = json.loads(raw)
        return [Finding(**item) for item in data]
