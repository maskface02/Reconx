"""
Phase 2: HTTP Probing & Tech Fingerprinting
For every live subdomain, fingerprint the HTTP surface.
"""
import json
import asyncio
import xml.etree.ElementTree as ET
from typing import List, Any, Dict
from pathlib import Path

from rich.console import Console

from core.workspace import Workspace
from core.models import HttpProbe, PhaseOutput
from core.utils import deduplicate_lines
from .base import BasePhase, PhaseException

console = Console()


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
        # Check Phase 1 output FIRST before printing any banners
        phase1_data = self.workspace.load_phase_output(1)
        if not phase1_data:
            raise PhaseException("No Phase 1 output found. Run 'python3 main.py run -p 1 --force' first.")
        
        # Now safe to start phase
        self.logger.phase_start(self.name, target=self.target)
        
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
        
        # Extract IPs for port scanning from httpx results (host_ip = actual IP httpx connected to)
        # This ensures masscan scans the same IP that responded to httpx
        ips = list(set([r.get('host_ip') for r in httpx_results if r.get('host_ip')]))
        
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
    
    async def _scan_ports(self, ips: List[str]) -> Dict[str, Dict]:
        """Scan ports using masscan and nmap. Returns {ip: {"ports": [], "services": []}}"""
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
                '-p', 'T:1-1000,U:1-1000',
                '--rate', '5000',
                '-oJ', str(masscan_output)
            ]
            
            cmd_str = ' '.join(cmd)
            self.logger.tool_start('masscan', cmd_str)
            
            self.logger.debug(f"Running masscan with {len(ips)} IPs")
            result = await self.runner.run('masscan', cmd, masscan_output)
            
            self.logger.debug(f"masscan result: success={result.success}, returncode={result.returncode}")
            
            if result.success and masscan_output.exists():
                try:
                    with open(masscan_output, 'r') as f:
                        content = f.read().strip()
                        if content:
                            # masscan outputs JSONL format (one JSON object per line)
                            for line in content.split('\n'):
                                line = line.strip()
                                if line and line != '[' and line != ']' and line != ',':
                                    try:
                                        entry = json.loads(line)
                                        ip = entry.get('ip')
                                        ports = [p['port'] for p in entry.get('ports', [])]
                                        if ip:
                                            results[ip] = {'ports': ports, 'services': []}
                                    except json.JSONDecodeError:
                                        pass
                    self.logger.tool_end('masscan', str(masscan_output), len(results))
                except Exception as e:
                    self.logger.warning(f"masscan parse failed: {e}")
                    self.logger.tool_end('masscan', str(masscan_output), 0)
            else:
                self.logger.warning(f"masscan failed: {result.stderr or 'unknown error'}")
                self.logger.tool_end('masscan', str(masscan_output), 0)
        else:
            self.logger.tool_skipped('masscan', 'not installed')
        
        # Run nmap on discovered open ports
        if results and self.tool_available('nmap'):
            # Get unique IPs with open ports
            unique_ips = list(results.keys())
            
            open_ports_file = self.workspace.get_raw_file("open_ports.txt")
            with open(open_ports_file, 'w') as f:
                f.write('\n'.join(unique_ips))
            
            # Get all ports that need scanning
            all_ports = set()
            for data in results.values():
                if isinstance(data, dict):
                    all_ports.update(data.get('ports', []))
                else:
                    all_ports.update(data)
            ports_str = ','.join(map(str, sorted(all_ports)))
            
            nmap_output = self.workspace.get_raw_file("nmap_out.xml")
            cmd = [
                self.get_tool_path('nmap'),
                '-sV',           # Service version detection
                '-T4',           # Aggressive timing
                '-iL', str(open_ports_file),
                '-p', ports_str,  # Scan only the ports found by masscan
                '-oX', '-'       # Output to stdout (captured by runner)
            ]
            
            cmd_str = ' '.join(cmd)
            self.logger.tool_start('nmap', cmd_str)
            
            result = await self.runner.run('nmap', cmd, nmap_output)
            
            # Parse nmap XML output to extract service info
            if result.success and nmap_output.exists():
                try:
                    tree = ET.parse(nmap_output)
                    root = tree.getroot()
                    for host in root.findall('.//host'):
                        ip_elem = host.find('address')
                        if ip_elem is not None:
                            ip = ip_elem.get('addr')
                            services = []
                            for port in host.findall('.//port'):
                                svc_elem = port.find('service')
                                if svc_elem is not None:
                                    name = svc_elem.get('name', '')
                                    product = svc_elem.get('product', '')
                                    version = svc_elem.get('version', '')
                                    
                                    # Build service string - prefer product over name, add version if available
                                    if product:
                                        service = product
                                        if version:
                                            service += f" {version}"
                                    elif name:
                                        service = name
                                        if version:
                                            service += f" {version}"
                                    else:
                                        continue
                                    
                                    # Skip protocol names (http, https, etc.)
                                    if service.lower() in ('http', 'https', 'tcp', 'udp'):
                                        continue
                                    
                                    if service and service not in services:
                                        services.append(service)
                            
                            if ip in results and services:
                                # Remove similar duplicates (e.g., "AWS Elastic Load Balancing" vs "awselb/2.0")
                                cleaned = []
                                for s in services:
                                    is_duplicate = False
                                    for existing in cleaned:
                                        # If one is abbreviation of another, skip the shorter
                                        if s.lower() in existing.lower() or existing.lower() in s.lower():
                                            is_duplicate = True
                                            break
                                    if not is_duplicate:
                                        cleaned.append(s)
                                results[ip]['services'] = cleaned
                    self.logger.tool_end('nmap', str(nmap_output), len(results))
                except Exception as e:
                    self.logger.debug(f"nmap XML parse error: {e}")
                    self.logger.tool_end('nmap', str(nmap_output), 0)
            else:
                self.logger.tool_end('nmap', str(nmap_output), 0)
        elif not results:
            pass  # No ports found from masscan
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
        
        self.logger.tool_start('wafw00f', f"Scanning {len(sample_urls)} URLs")
        
        for url in sample_urls:
            output_file = self.workspace.get_raw_file(f"wafw00f_{url.replace('://', '_').replace('/', '_')}.json")
            
            cmd = [
                self.get_tool_path('wafw00f'),
                url,
                '-f', 'json',
                '-o', '-'  # Output JSON to stdout
            ]
            
            result = await self.runner.run('wafw00f', cmd, output_file)
            
            # JSON output is in stdout, not in file
            if result.success and result.stdout:
                self.logger.debug(f"wafw00f stdout for {url}: {result.stdout[:200]}")
                try:
                    data = json.loads(result.stdout)
                    if data and len(data) > 0:
                        waf = data[0].get('firewall', '')
                        if waf:
                            results[url] = waf
                            self.logger.debug(f"Detected WAF for {url}: {waf}")
                except (json.JSONDecodeError, IndexError) as e:
                    self.logger.debug(f"wafw00f parse error for {url}: {e}")
        
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
            
            # Get ports and services - use host_ip (the resolved IP) to match port_results keys
            ip = result.get('host_ip', '')
            port_data = port_results.get(ip, {})
            ports = port_data.get('ports', []) if isinstance(port_data, dict) else []
            services = port_data.get('services', []) if isinstance(port_data, dict) else []
            
            probe = HttpProbe(
                url=url,
                status_code=result.get('status_code', 0),
                title=result.get('title', ''),
                tech=tech,
                waf=waf if waf else None,
                waf_bypass_needed=bool(waf),
                ports=ports,
                services=services,
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
