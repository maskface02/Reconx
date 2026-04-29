"""
Phase 1: Subdomain & Asset Discovery
Builds a complete, deduplicated, alive-verified list of subdomains.
"""
import re

import json
import asyncio
from typing import List, Any
from pathlib import Path

from core.workspace import Workspace
from core.models import Subdomain, PhaseOutput
from core.utils import deduplicate_lines, is_in_scope, parse_amass_output
from core.logger import get_logger
from core.runner import AsyncRunner
from .base import BasePhase, PhaseException


class Phase1Discovery(BasePhase):
    """Phase 1: Discover subdomains and assets."""
    
    name = "Subdomain & Asset Discovery"
    phase_number = 1
    output_file = "phase1_output.json"
    
    def __init__(self, workspace: Workspace, config: dict):
        super().__init__(workspace, config)
        self.target = config['target']
        self.scope = config.get('scope') or [f"*.{self.target}", self.target]
        self.exclude = config.get('exclude', [])
        self.dns_data = {}  # Store DNS resolution data (ip, cname, asn)
    
    async def run(self) -> PhaseOutput:
        """Execute Phase 1: Subdomain discovery."""
        self.logger.phase_start(self.name, target=self.target)
        
        all_subdomains: set = set()
        source_map: dict = {}  # subdomain -> list of sources
        
        # Run all discovery tools in parallel
        tasks = []
        tool_names = []
        source_map: dict = {}  # subdomain -> list of sources
        
        # Subfinder
        if self.tool_available('subfinder'):
            tasks.append(self._run_subfinder())
            tool_names.append('subfinder')
        else:
            self.logger.tool_skipped('subfinder', 'not installed')
        
        # Amass passive
        if self.tool_available('amass'):
            tasks.append(self._run_amass_passive())
            tool_names.append('amass_passive')
            tasks.append(self._run_amass_active())
            tool_names.append('amass_active')
        else:
            self.logger.tool_skipped('amass', 'not installed')
        
        # Assetfinder
        if self.tool_available('assetfinder'):
            tasks.append(self._run_assetfinder())
            tool_names.append('assetfinder')
        else:
            self.logger.tool_skipped('assetfinder', 'not installed')
        
        # crt.sh (always runs, no tool needed)
        tasks.append(self._run_crtsh())
        tool_names.append('crt.sh')
        
        # Chaos API (if key configured)
        if self.config.get('PDCP_API_KEY'):
            tasks.append(self._run_chaos())
            tool_names.append('chaos')
        
        # Wait for all discovery tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results with source tracking
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Discovery task failed: {result}")
                continue
            tool_name = tool_names[idx] if idx < len(tool_names) else 'unknown'
            for subdomain in result:
                subdomain = subdomain.lower().strip()
                if subdomain and is_in_scope(subdomain, self.scope, self.exclude):
                    all_subdomains.add(subdomain)
                    # Track sources properly
                    if subdomain not in source_map:
                        source_map[subdomain] = []
                    if tool_name not in source_map[subdomain]:
                        source_map[subdomain].append(tool_name)
        
        if not all_subdomains:
            self.logger.warning("No subdomains discovered")
            return PhaseOutput(
                phase=self.name,
                count=0,
                output_file=str(self.workspace.get_phase_output(1))
            )
        
        self.logger.info(f"Discovered {len(all_subdomains)} unique subdomains")
        
        # Save merged subdomains for DNS resolution (deduplicated)
        merged_file = self.workspace.get_raw_file("subdomains_merged.txt")
        unique_subs = sorted(set(all_subdomains))
        with open(merged_file, 'w') as f:
            f.write('\n'.join(unique_subs))
        
        # DNS resolution with dnsx
        self.logger.tool_start('dnsx', f'resolving {len(unique_subs)} subdomains')
        resolved = await self._resolve_dns(merged_file)
        
        # Deduplicate resolved subdomains before httpx
        unique_resolved = sorted(set(resolved))
        
        # Alive check with httpx
        self.logger.tool_start('httpx', f'checking {len(unique_resolved)} subdomains')
        live_subdomains = await self._check_alive(unique_resolved)
        
        # Build Subdomain objects (deduplicate first)
        unique_live = list(dict.fromkeys(live_subdomains))
        subdomain_objects = []
        for sub in unique_live:
            # Normalize URL to hostname for DNS lookup
            hostname = sub.replace('https://', '').replace('http://', '').rstrip('/')
            
            # Get DNS data for this subdomain
            dns_info = self.dns_data.get(hostname, {})
            
            # Convert list to comma-separated string for IP field (model expects str, not list)
            ip_value = dns_info.get('ip')
            if isinstance(ip_value, list) and ip_value:
                ip_value = ip_value[0]
            
            cname_value = dns_info.get('cname')
            if isinstance(cname_value, list) and cname_value:
                cname_value = cname_value[0]
            
            asn_value = dns_info.get('asn')
            if isinstance(asn_value, list) and asn_value:
                asn_value = str(asn_value[0])
            elif isinstance(asn_value, dict):
                asn_value = str(asn_value.get('asn', ''))
            
            subdomain_objects.append(Subdomain(
                subdomain=sub,
                ip=ip_value,
                cname=cname_value,
                asn=asn_value,
                sources=source_map.get(hostname, []),
                alive=True
            ))
        
        # Save output
        output_data = [s.model_dump() for s in subdomain_objects]
        self.workspace.save_phase_output(1, output_data)
        
        self.logger.phase_end(self.name, str(self.workspace.get_phase_output(1)), len(subdomain_objects))
        
        return PhaseOutput(
            phase=self.name,
            count=len(subdomain_objects),
            output_file=str(self.workspace.get_phase_output(1))
        )
    
    async def _run_subfinder(self) -> List[str]:
        """Run subfinder for subdomain discovery."""
        output_file = self.workspace.get_raw_file("subfinder.txt")

        cmd = [
            self.get_tool_path('subfinder'),
            '-d', self.target,
            '-silent',
            '-o', str(output_file)
        ]

        # Subfinder needs more time - use a dedicated runner
        subfinder_runner = AsyncRunner(
            rate_limit=self.runner.rate_limit,
            timeout=300
        )
        result = await subfinder_runner.run('subfinder', cmd, output_file)

        if result.success and output_file.exists():
            with open(output_file, 'r') as f:
                subdomains = [line.strip() for line in f if line.strip()]
            self.logger.tool_end('subfinder', str(output_file), len(subdomains))
            return subdomains

        # Fallback: parse stdout if output file is empty
        if result.stdout:
            subdomains = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            if subdomains and output_file.exists():
                with open(output_file, 'w') as f:
                    f.write('\n'.join(subdomains))
            self.logger.tool_end('subfinder', str(output_file), len(subdomains))
            return subdomains

        if result.error_message:
            self.logger.error(f"subfinder failed: {result.error_message}")
        return []
    
    async def _run_amass_passive(self) -> List[str]:
        """Run amass passive enumeration."""
        output_file = self.workspace.get_raw_file("amass_passive.txt")

        cmd = [
            self.get_tool_path('amass'),
            'enum', '-passive',
            '-d', self.target,
            '-o', str(output_file)
        ]

        # Amass needs more time - use a dedicated runner with higher timeout
        amass_runner = AsyncRunner(
            rate_limit=self.runner.rate_limit,
            timeout=300
        )
        result = await amass_runner.run('amass_passive', cmd, output_file)
        
        # Read output file even if the process timed out - amass writes incrementally
        if output_file.exists() and output_file.stat().st_size > 0:
            with open(output_file, 'r') as f:
                content = f.read()
            subdomains = parse_amass_output(content)
            if subdomains:
                self.logger.tool_end('amass_passive', str(output_file), len(subdomains))
                return subdomains
            # No valid domains found in output - log warning
            self.logger.warning(f"amass_passive: no valid subdomains found in output (got DNS records instead)")
            self.logger.tool_end('amass_passive', str(output_file), 0)
        
        # Fallback: parse stdout if output file is empty
        if result.stdout:
            subdomains = parse_amass_output(result.stdout)
            if subdomains:
                if output_file.exists():
                    with open(output_file, 'w') as f:
                        f.write('\n'.join(subdomains))
                self.logger.tool_end('amass_passive', str(output_file), len(subdomains))
                return subdomains
        
        if result.error_message:
            self.logger.warning(f"amass_passive failed: {result.error_message}")
        self.logger.tool_end('amass_passive', str(output_file), 0)
        return []
    
    async def _run_amass_active(self) -> List[str]:
        """Run amass active enumeration."""
        output_file = self.workspace.get_raw_file("amass_active.txt")

        cmd = [
            self.get_tool_path('amass'),
            'enum', '-active',
            '-d', self.target,
            '-o', str(output_file)
        ]

        # Amass needs more time - use a dedicated runner
        amass_runner = AsyncRunner(
            rate_limit=self.runner.rate_limit,
            timeout=300
        )
        result = await amass_runner.run('amass_active', cmd, output_file)
        
        # Read output file even if the process timed out - amass writes incrementally
        if output_file.exists() and output_file.stat().st_size > 0:
            with open(output_file, 'r') as f:
                content = f.read()
            subdomains = parse_amass_output(content)
            if subdomains:
                self.logger.tool_end('amass_active', str(output_file), len(subdomains))
                return subdomains
            # No valid domains found in output - log warning
            self.logger.warning(f"amass_active: no valid subdomains found in output (got DNS records instead)")
            self.logger.tool_end('amass_active', str(output_file), 0)
        
        # Fallback: parse stdout if output file is empty
        if result.stdout:
            subdomains = parse_amass_output(result.stdout)
            if subdomains:
                if output_file.exists():
                    with open(output_file, 'w') as f:
                        f.write('\n'.join(subdomains))
                self.logger.tool_end('amass_active', str(output_file), len(subdomains))
                return subdomains
        
        if result.error_message:
            self.logger.warning(f"amass_active failed: {result.error_message}")
        self.logger.tool_end('amass_active', str(output_file), 0)
        return []
    
    async def _run_assetfinder(self) -> List[str]:
        """Run assetfinder for subdomain discovery."""
        output_file = self.workspace.get_raw_file("assetfinder.txt")

        # Write target to temp file for stdin
        input_file = self.workspace.get_raw_file("assetfinder_input.txt")
        with open(input_file, 'w') as f:
            f.write(self.target)

        cmd = [
            self.get_tool_path('assetfinder'),
            '--subs-only'
        ]

        result = await self.runner.run(
            'assetfinder', cmd,
            input_file=input_file
        )

        if result.success and result.stdout:
            subdomains = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            if subdomains:
                with open(output_file, 'w') as f:
                    f.write('\n'.join(subdomains))
                self.logger.tool_end('assetfinder', str(output_file), len(subdomains))
                return subdomains

        if result.error_message:
            self.logger.error(f"assetfinder failed: {result.error_message}")
        return []
    
    async def _run_crtsh(self) -> List[str]:
        """Query crt.sh using crt.sh tool."""
        output_file = self.workspace.get_raw_file("crt.sh.txt")
        
        # Path to crt.sh tool output directory
        crt_output_dir = Path.home() / ".local" / "opt" / "crtsh" / "output"
        crt_output_file = crt_output_dir / f"domain.{self.target}.txt"
        
        # Use dedicated runner with 180s timeout for crt.sh
        crt_runner = AsyncRunner(
            rate_limit=self.runner.rate_limit,
            timeout=300
        )
        
        cmd = ['crt.sh', '-d', self.target]
        
        await crt_runner.run('crt.sh', cmd)
        
        # Read from output file instead of stdout
        subdomains = []
        if crt_output_file.exists():
            with open(crt_output_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('*'):
                        subdomains.append(line)
            
            subdomains = list(set(subdomains))
            
            if subdomains:
                # Save raw output to workspace
                with open(output_file, 'w') as f:
                    f.write('\n'.join(subdomains))
                self.logger.tool_end('crt.sh', str(output_file), len(subdomains))
            else:
                self.logger.tool_end('crt.sh', str(output_file), 0)
                self.logger.warning("crt.sh returned 0 items (API may be down)")
        else:
            # No output file created - likely API error
            self.logger.tool_end('crt.sh', str(output_file), 0)
            self.logger.warning("crt.sh returned 0 items (API may be down)")
        
        return subdomains
    
    async def _run_chaos(self) -> List[str]:
        """Query Chaos dataset API."""
        output_file = self.workspace.get_raw_file("chaos.txt")
        api_key = self.config.get('PDCP_API_KEY')

        if not api_key:
            return []

        url = f"https://dns.projectdiscovery.io/dns/{self.target}/subdomains"

        result = await self.runner.fetch_url(
            url,
            headers={"Authorization": api_key},
            tool_name="chaos"
        )

        subdomains = []
        if result['success']:
            try:
                data = json.loads(result['body'])
                raw_subdomains = data.get('subdomains', [])
                for sub in raw_subdomains:
                    sub = sub.strip()
                    if not sub or sub == '*':
                        continue
                    # Chaos API returns subdomains like "*.api", "api", "blog"
                    # We need to format them properly
                    if sub.startswith('*.'):
                        # Wildcard: *.api -> *.api.target.com
                        subdomains.append(f"{sub}.{self.target}")
                    elif sub == self.target:
                        # Exact match (e.g. "spendesk.com")
                        subdomains.append(sub)
                    else:
                        # Regular subdomain
                        subdomains.append(f"{sub}.{self.target}")

                with open(output_file, 'w') as f:
                    f.write('\n'.join(subdomains))
                self.logger.tool_end('chaos', str(output_file), len(subdomains))
            except json.JSONDecodeError:
                pass

        return subdomains
    
    async def _resolve_dns(self, input_file: Path) -> List[str]:
        """Resolve DNS for discovered subdomains using dnsx."""
        output_file = self.workspace.get_raw_file("subdomains_resolved.txt")
        
        if not self.tool_available('dnsx'):
            self.logger.tool_skipped('dnsx', 'not installed - using all subdomains')
            with open(input_file, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        
        # Get PDCP API key from config for ASN lookups
        pdcp_config_key = 'PDCP_API_KEY'
        
        # Set up environment with API key if available
        env = None
        pdcp_api_key = self.config.get(pdcp_config_key)
        if pdcp_api_key:
            env = {'PDCP_API_KEY': pdcp_api_key}
        
        cmd = [
            self.get_tool_path('dnsx'),
            '-l', str(input_file),
            '-silent',
            '-re',
            '-asn',
            '-cname',
            '-a',
            '-aaaa',
            '-o', str(output_file)
        ]
        
        result = await self.runner.run('dnsx', cmd, output_file, env=env)
        
        resolved = []
        self.dns_data = {}  # Store DNS data for later use
        
        if result.success and output_file.exists() and output_file.stat().st_size > 0:
            seen = set()
            
            with open(output_file, 'r') as f:
                for line in f:
                    # Line format: "domain [A] [IP] [ASXXXX, name, country]"
                    # ANSI codes are literal strings like [35m, [32m, [0m
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    # Extract subdomain (first token before any bracket)
                    subdomain = line.split()[0] if line.split() else ''
                    if not subdomain or subdomain in seen:
                        continue
                    seen.add(subdomain)
                    
                    # Extract IP - find first IP pattern
                    ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                    ip_value = ip_match.group(1) if ip_match else None
                    
                    # Extract ASN
                    asn_match = re.search(r'(AS\d+)', line)
                    asn_value = asn_match.group(1) if asn_match else None
                    
                    resolved.append(subdomain)
                    self.dns_data[subdomain] = {
                        'ip': ip_value,
                        'aaaa': None,
                        'cname': None,
                        'asn': asn_value,
                    }
            
            self.logger.tool_end('dnsx', str(output_file), len(resolved))
            return resolved
        
        # Fallback to input
        with open(input_file, 'r') as f:
            resolved = [line.strip() for line in f if line.strip()]
        self.logger.tool_end('dnsx', str(input_file), len(resolved))
        return resolved
    
    async def _check_alive(self, subdomains: List[str]) -> List[str]:
        """Check which subdomains are alive using httpx."""
        output_file = self.workspace.get_raw_file("subdomains_live.txt")
        
        # Write input for httpx
        input_file = self.workspace.get_raw_file("httpx_input.txt")
        with open(input_file, 'w') as f:
            f.write('\n'.join(subdomains))
        
        if not self.tool_available('httpx'):
            self.logger.tool_skipped('httpx', 'not installed - assuming all resolved are alive')
            return subdomains
        
        # Use dedicated runner with 180s timeout for httpx
        httpx_runner = AsyncRunner(
            rate_limit=self.runner.rate_limit,
            timeout=300
        )
        cmd = [
            self.get_tool_path('httpx'),
            '-l', str(input_file),
            '-silent',
            '-no-color',
            '-o', str(output_file),
            '-sc',
            '-cl',
            '-ct', '5'
        ]
        
        result = await httpx_runner.run('httpx', cmd, output_file)
        
        if result.success and output_file.exists() and output_file.stat().st_size > 0:
            with open(output_file, 'r') as f:
                live = []
                for line in f:
                    line = line.strip()
                    # Format now: "url [status_code]" without colors
                    # Check if line looks valid: starts with http and contains status code in brackets
                    if line and line.startswith('http') and '[' in line and ']' in line:
                        url = line.split('[')[0].strip()
                        live.append(url)
            # Deduplicate live URLs before returning
            live = list(dict.fromkeys(live))
            self.logger.tool_end('httpx', str(output_file), len(live))
            return live
        
        # Fallback: try reading from stdout if output file is empty
        if result.stdout:
            live = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                # Format now: "url [status_code]" without colors
                if line and line.startswith('http') and '[' in line and ']' in line:
                    url = line.split('[')[0].strip()
                    live.append(url)
            live = list(dict.fromkeys(live))
            self.logger.tool_end('httpx', str(output_file), len(live))
            return live
        
        # If nothing worked, return empty list
        self.logger.tool_end('httpx', str(output_file), 0)
        return []
    
    def parse_output(self, raw: str) -> List[Any]:
        """Parse raw output into Subdomain objects."""
        data = json.loads(raw)
        return [Subdomain(**item) for item in data]
