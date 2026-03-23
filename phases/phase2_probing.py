"""
Phase 2: HTTP Probing & Tech Fingerprinting
For every live subdomain, fingerprint the HTTP surface.
"""
import json
import asyncio
from typing import List, Any, Dict
from pathlib import Path

from core.workspace import Workspace
from core.models import HttpProbe, PhaseOutput
from core.utils import deduplicate_lines
from .base import BasePhase


class Phase2Probing(BasePhase):
    """Phase 2: HTTP probing and technology fingerprinting."""
    
    name = "HTTP Probing & Tech Fingerprinting"
    phase_number = 2
    input_file = "phase1_output.json"
    output_file = "phase2_output.json"
    
    def __init__(self, workspace: Workspace, config: dict):
        super().__init__(workspace, config)
        self.target = config['target']
    
    async def run(self) -> PhaseOutput:
        """Execute Phase 2: HTTP probing."""
        self.logger.phase_start(self.name, target=self.target)
        
        # Load Phase 1 output
        phase1_data = self.workspace.load_phase_output(1)
        if not phase1_data:
            self.logger.warning("No Phase 1 output found, cannot proceed")
            return PhaseOutput(
                phase=self.name,
                count=0,
                output_file=str(self.workspace.get_phase_output(2))
            )
        
        # Extract subdomains
        subdomains = [item['subdomain'] for item in phase1_data if item.get('alive', False)]
        
        if not subdomains:
            self.logger.warning("No live subdomains found")
            return PhaseOutput(
                phase=self.name,
                count=0,
                output_file=str(self.workspace.get_phase_output(2))
            )
        
        self.logger.info(f"Probing {len(subdomains)} subdomains")
        
        # Create URLs from subdomains
        urls = []
        for sub in subdomains:
            if not sub.startswith(('http://', 'https://')):
                urls.append(f"https://{sub}")
                urls.append(f"http://{sub}")
            else:
                urls.append(sub)
        
        # Save URLs for httpx
        urls_file = self.workspace.workspace_path / "urls.txt"
        with open(urls_file, 'w') as f:
            f.write('\n'.join(urls))
        
        # Run httpx for detailed probing
        httpx_results = await self._run_httpx(urls_file)
        
        # Extract IPs for port scanning
        ips = list(set([item.get('ip') for item in phase1_data if item.get('ip')]))
        
        # Run port scanning (optional, don't block if tools missing)
        port_results = {}
        if ips:
            port_results = await self._scan_ports(ips)
        
        # Run WAF detection
        waf_results = await self._detect_waf([r['url'] for r in httpx_results])
        
        # Merge results into HttpProbe objects
        probes = self._merge_results(httpx_results, port_results, waf_results)
        
        # Save output
        output_data = [p.model_dump() for p in probes]
        self.workspace.save_phase_output(2, output_data)
        
        # Save flat URLs file for downstream phases
        live_urls = [p.url for p in probes if p.status_code > 0]
        self.workspace.save_text_file("urls.txt", live_urls)
        
        self.logger.phase_end(self.name, str(self.workspace.get_phase_output(2)), len(probes))
        
        return PhaseOutput(
            phase=self.name,
            count=len(probes),
            output_file=str(self.workspace.get_phase_output(2))
        )
    
    async def _run_httpx(self, urls_file: Path) -> List[Dict]:
        """Run httpx for HTTP probing."""
        output_file = self.workspace.get_raw_file("httpx_out.jsonl")
        
        if not self.tool_available('httpx'):
            self.logger.tool_skipped('httpx', 'not installed')
            # Return basic probe data from URLs
            with open(urls_file, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
            return [{'url': url, 'status_code': 0} for url in urls]
        
        cmd = [
            self.get_tool_path('httpx'),
            '-l', str(urls_file),
            '-tech-detect',
            '-status-code',
            '-title',
            '-content-length',
            '-follow-redirects',
            '-json',
            '-o', str(output_file)
        ]
        
        result = await self.runner.run('httpx', cmd, output_file)
        
        results = []
        if result.success and output_file.exists():
            with open(output_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            results.append(data)
                        except json.JSONDecodeError:
                            continue
        
        self.logger.tool_end('httpx', str(output_file), len(results))
        return results
    
    async def _scan_ports(self, ips: List[str]) -> Dict[str, List[int]]:
        """Scan ports using masscan and nmap."""
        results = {}
        
        # Save IPs for scanning
        ips_file = self.workspace.get_raw_file("ips.txt")
        with open(ips_file, 'w') as f:
            f.write('\n'.join(ips))
        
        # Try masscan first
        masscan_output = self.workspace.get_raw_file("masscan_out.json")
        
        if self.tool_available('masscan'):
            cmd = [
                self.get_tool_path('masscan'),
                '-iL', str(ips_file),
                '-p1-65535',
                '--rate', '1000',
                '-oJ', str(masscan_output)
            ]
            
            result = await self.runner.run('masscan', cmd, masscan_output)
            
            if result.success and masscan_output.exists():
                try:
                    with open(masscan_output, 'r') as f:
                        data = json.load(f)
                        for entry in data:
                            ip = entry.get('ip')
                            ports = [p['port'] for p in entry.get('ports', [])]
                            if ip:
                                results[ip] = ports
                    self.logger.tool_end('masscan', str(masscan_output), len(results))
                except json.JSONDecodeError:
                    pass
        else:
            self.logger.tool_skipped('masscan', 'not installed')
        
        # Run nmap on discovered open ports
        if results and self.tool_available('nmap'):
            open_ports_file = self.workspace.get_raw_file("open_ports.txt")
            with open(open_ports_file, 'w') as f:
                for ip, ports in results.items():
                    for port in ports:
                        f.write(f"{ip}:{port}\n")
            
            nmap_output = self.workspace.get_raw_file("nmap_out.json")
            cmd = [
                self.get_tool_path('nmap'),
                '-sV',
                '-iL', str(open_ports_file),
                '-oJ', str(nmap_output)
            ]
            
            result = await self.runner.run('nmap', cmd, nmap_output)
            
            if result.success:
                self.logger.tool_end('nmap', str(nmap_output), len(results))
        else:
            self.logger.tool_skipped('nmap', 'not installed')
        
        return results
    
    async def _detect_waf(self, urls: List[str]) -> Dict[str, str]:
        """Detect WAF using wafw00f."""
        results = {}
        
        if not self.tool_available('wafw00f'):
            self.logger.tool_skipped('wafw00f', 'not installed')
            return results
        
        # Sample URLs to avoid too many requests
        sample_urls = urls[:20] if len(urls) > 20 else urls
        
        for url in sample_urls:
            output_file = self.workspace.get_raw_file(f"wafw00f_{url.replace('://', '_').replace('/', '_')}.json")
            
            cmd = [
                self.get_tool_path('wafw00f'),
                url,
                '-o', str(output_file)
            ]
            
            result = await self.runner.run(f'wafw00f_{url}', cmd, output_file)
            
            if result.success and output_file.exists():
                try:
                    with open(output_file, 'r') as f:
                        data = json.load(f)
                        if data and len(data) > 0:
                            waf = data[0].get('firewall', '')
                            if waf:
                                results[url] = waf
                except (json.JSONDecodeError, IndexError):
                    continue
        
        self.logger.tool_end('wafw00f', None, len(results))
        return results
    
    def _merge_results(
        self, 
        httpx_results: List[Dict], 
        port_results: Dict[str, List[int]],
        waf_results: Dict[str, str]
    ) -> List[HttpProbe]:
        """Merge results from various tools into HttpProbe objects."""
        probes = []
        
        for result in httpx_results:
            url = result.get('url', '')
            
            # Extract tech stack
            tech = []
            if 'tech' in result:
                tech = result['tech'] if isinstance(result['tech'], list) else [result['tech']]
            
            # Get WAF info
            waf = waf_results.get(url, '')
            
            # Get ports
            ip = result.get('host', '')
            ports = port_results.get(ip, [])
            
            probe = HttpProbe(
                url=url,
                status_code=result.get('status_code', 0),
                title=result.get('title', ''),
                tech=tech,
                waf=waf if waf else None,
                waf_bypass_needed=bool(waf),
                ports=ports,
                cdn=result.get('cdn', False),
                ip=ip,
                content_length=result.get('content_length', 0)
            )
            probes.append(probe)
        
        return probes
    
    def parse_output(self, raw: str) -> List[Any]:
        """Parse raw output into HttpProbe objects."""
        data = json.loads(raw)
        return [HttpProbe(**item) for item in data]
