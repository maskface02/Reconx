"""
Phase 1: Subdomain & Asset Discovery
Builds a complete, deduplicated, alive-verified list of subdomains.
"""
import json
import asyncio
from typing import List, Any, Tuple
from pathlib import Path

from core.workspace import Workspace
from core.models import Subdomain, PhaseOutput
from core.utils import deduplicate_lines, parse_crtsh_json, is_in_scope
from core.logger import get_logger
from core.runner import AsyncRunner
from .base import BasePhase, PhaseException


# Free ASN lookup via ipinfo.io (no auth needed, 1000 req/month limit)
ASN_API_URL = "https://ipinfo.io/{ip}/json"


class Phase1Discovery(BasePhase):
    """Phase 1: Discover subdomains and assets."""
    
    name = "Subdomain & Asset Discovery"
    phase_number = 1
    output_file = "phase1_output.json"
    
    def __init__(self, workspace: Workspace, config: dict):
        super().__init__(workspace, config)
        self.target = config['target']
        self.scope = config.get('scope', [f"*.{self.target}", self.target])
        self.exclude = config.get('exclude', [])
    
    async def run(self) -> PhaseOutput:
        """Execute Phase 1: Subdomain discovery."""
        self.logger.phase_start(self.name, target=self.target)

        all_subdomains: set = set()
        source_map: dict = {}  # subdomain -> list of sources

        # Helper to wrap tool results with source name
        async def _with_source(coro, source_name: str) -> Tuple[List[str], str]:
            subs = await coro
            return subs, source_name

        # Build tasks with source tracking
        tasks = []

        # Subfinder
        if self.tool_available('subfinder'):
            tasks.append(_with_source(self._run_subfinder(), 'subfinder'))
        else:
            self.logger.tool_skipped('subfinder', 'not installed')

        # Amass passive
        if self.tool_available('amass'):
            tasks.append(_with_source(self._run_amass_passive(), 'amass'))
        else:
            self.logger.tool_skipped('amass', 'not installed')

        # Assetfinder
        if self.tool_available('assetfinder'):
            tasks.append(_with_source(self._run_assetfinder(), 'assetfinder'))
        else:
            self.logger.tool_skipped('assetfinder', 'not installed')

        # crt.sh (always runs, no tool needed)
        tasks.append(_with_source(self._run_crtsh(), 'crt.sh'))

        # Chaos API (if key configured)
        if self.config.get('chaos_api_key'):
            tasks.append(_with_source(self._run_chaos(), 'chaos'))

        # Wait for all discovery tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results with source tracking
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Discovery task failed: {result}")
                continue
            subdomains, source = result
            for subdomain in subdomains:
                subdomain = subdomain.lower().strip()
                if subdomain and is_in_scope(subdomain, self.scope, self.exclude):
                    all_subdomains.add(subdomain)
                    if subdomain not in source_map:
                        source_map[subdomain] = []
                    if source not in source_map[subdomain]:
                        source_map[subdomain].append(source)
        
        if not all_subdomains:
            self.logger.warning("No subdomains discovered")
            return PhaseOutput(
                phase=self.name,
                count=0,
                output_file=str(self.workspace.get_phase_output(1))
            )
        
        self.logger.info(f"Discovered {len(all_subdomains)} unique subdomains")
        
        # Save merged subdomains for DNS resolution
        merged_file = self.workspace.get_raw_file("subdomains_merged.txt")
        with open(merged_file, 'w') as f:
            f.write('\n'.join(sorted(all_subdomains)))

        # DNS resolution with dnsx (extract IPs, CNAMEs, ASN)
        resolved, info_map = await self._resolve_dns(merged_file)

        # Alive check with httpx
        live_subdomains = await self._check_alive(resolved, info_map)

        # ASN lookup for all resolved IPs
        await self._lookup_asn(info_map)

        # Build Subdomain objects with IPs, CNAMEs, and ASN
        subdomain_objects = []
        for sub in live_subdomains:
            info = info_map.get(sub, {})
            subdomain_objects.append(Subdomain(
                subdomain=sub,
                sources=source_map.get(sub, []),
                alive=True,
                ip=info.get('ip'),
                cname=info.get('cname'),
                asn=info.get('asn')
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
        if output_file.exists():
            with open(output_file, 'r') as f:
                subdomains = [line.strip() for line in f if line.strip()]
            if subdomains:
                self.logger.tool_end('amass_passive', str(output_file), len(subdomains))
                return subdomains

        # Fallback: parse stdout if output file is empty
        if result.stdout:
            subdomains = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            if subdomains:
                if output_file.exists():
                    with open(output_file, 'w') as f:
                        f.write('\n'.join(subdomains))
                self.logger.tool_end('amass_passive', str(output_file), len(subdomains))
                return subdomains

        if result.error_message:
            self.logger.error(f"amass_passive failed: {result.error_message}")
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
        if output_file.exists():
            with open(output_file, 'r') as f:
                subdomains = [line.strip() for line in f if line.strip()]
            if subdomains:
                self.logger.tool_end('amass_active', str(output_file), len(subdomains))
                return subdomains

        # Fallback: parse stdout if output file is empty
        if result.stdout:
            subdomains = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            if subdomains:
                if output_file.exists():
                    with open(output_file, 'w') as f:
                        f.write('\n'.join(subdomains))
                self.logger.tool_end('amass_active', str(output_file), len(subdomains))
                return subdomains

        if result.error_message:
            self.logger.error(f"amass_active failed: {result.error_message}")
        return []
    
    async def _run_assetfinder(self) -> List[str]:
        """Run assetfinder for subdomain discovery."""
        output_file = self.workspace.get_raw_file("assetfinder.txt")

        # assetfinder requires domain as argument, not stdin
        cmd = [
            self.get_tool_path('assetfinder'),
            '--subs-only',
            self.target
        ]

        result = await self.runner.run('assetfinder', cmd, output_file)

        if result.success and output_file.exists():
            with open(output_file, 'r') as f:
                subdomains = [line.strip() for line in f if line.strip()]
            if subdomains:
                self.logger.tool_end('assetfinder', str(output_file), len(subdomains))
                return subdomains

        # Fallback: parse stdout if output file is empty
        if result.stdout:
            subdomains = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            if subdomains:
                if output_file.exists():
                    with open(output_file, 'w') as f:
                        f.write('\n'.join(subdomains))
                self.logger.tool_end('assetfinder', str(output_file), len(subdomains))
                return subdomains

        if result.error_message:
            self.logger.error(f"assetfinder failed: {result.error_message}")
        return []
    
    async def _run_crtsh(self) -> List[str]:
        """Query crt.sh for certificate transparency logs."""
        output_file = self.workspace.get_raw_file("crtsh.json")

        url = f"https://crt.sh/?q=%25.{self.target}&output=json"

        result = await self.runner.fetch_url(url, tool_name="crt.sh")
        
        subdomains = []
        if result['success']:
            subdomains = parse_crtsh_json(result['body'])
            # Save raw output
            with open(output_file, 'w') as f:
                f.write(result['body'])
            self.logger.tool_end('crtsh', str(output_file), len(subdomains))
        
        return subdomains
    
    async def _run_chaos(self) -> List[str]:
        """Query Chaos dataset API."""
        output_file = self.workspace.get_raw_file("chaos.txt")
        api_key = self.config.get('chaos_api_key')

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
    
    async def _resolve_dns(self, input_file: Path) -> tuple:
        """Resolve DNS for discovered subdomains using dnsx.

        Returns:
            Tuple of (resolved_subdomains, info_map) where info_map is {subdomain: {ip, cname, asn}}
        """
        output_file = self.workspace.get_raw_file("subdomains_resolved.json")

        if not self.tool_available('dnsx'):
            self.logger.tool_skipped('dnsx', 'not installed - using all subdomains')
            with open(input_file, 'r') as f:
                subs = [line.strip() for line in f if line.strip()]
            return subs, {}

        cmd = [
            self.get_tool_path('dnsx'),
            '-l', str(input_file),
            '-a', '-resp',
            '-cname',
            '-silent',
            '-json',
            '-o', str(output_file)
        ]

        result = await self.runner.run('dnsx', cmd, output_file)

        resolved = []
        info_map = {}
        if result.success and output_file.exists():
            with open(output_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        host = data.get('host', '')
                        # Skip netblock entries
                        if not host or '(netblock)' in host:
                            continue
                        # Extract clean hostname
                        host = host.split(' (')[0]
                        # Only keep subdomains that end with our target
                        if not (host == self.target or host.endswith(f'.{self.target}')):
                            continue
                        resolved.append(host)
                        # Extract info
                        info = {}
                        a_records = data.get('a', [])
                        if a_records:
                            info['ip'] = a_records[0]
                        cname_list = data.get('cname', [])
                        if cname_list:
                            info['cname'] = cname_list[0]
                        if info:
                            info_map[host] = info
                    except json.JSONDecodeError:
                        continue

            self.logger.tool_end('dnsx', str(output_file), len(resolved))
            return resolved, info_map

        # Fallback to input
        with open(input_file, 'r') as f:
            subs = [line.strip() for line in f if line.strip()]
        return subs, {}
    
    async def _check_alive(self, subdomains: List[str], info_map: dict) -> List[str]:
        """Check which subdomains are alive using httpx."""
        output_file = self.workspace.get_raw_file("subdomains_live.txt")

        # Write input for httpx
        input_file = self.workspace.get_raw_file("httpx_input.txt")
        with open(input_file, 'w') as f:
            f.write('\n'.join(subdomains))

        if not self.tool_available('httpx'):
            self.logger.tool_skipped('httpx', 'not installed - assuming all resolved are alive')
            return subdomains

        cmd = [
            self.get_tool_path('httpx'),
            '-l', str(input_file),
            '-silent',
            '-o', str(output_file)
        ]

        result = await self.runner.run('httpx', cmd, output_file)

        if result.success and output_file.exists():
            with open(output_file, 'r') as f:
                # Strip protocol (http:// or https://) and trailing paths to get clean hostnames
                live = []
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # Remove protocol
                    if line.startswith(('http://', 'https://')):
                        # Extract just the hostname
                        from urllib.parse import urlparse
                        try:
                            parsed = urlparse(line)
                            live.append(parsed.hostname)
                        except:
                            live.append(line.split('/')[2].split(':')[0])
                    else:
                        live.append(line.split('/')[0].split(':')[0])
            self.logger.tool_end('httpx', str(output_file), len(live))
            return live

        return subdomains

    async def _lookup_asn(self, info_map: dict):
        """Lookup ASN info for each unique IP using ipinfo.io."""
        # Collect unique IPs
        unique_ips = set()
        for info in info_map.values():
            ip = info.get('ip')
            if ip:
                unique_ips.add(ip)

        if not unique_ips:
            return

        self.logger.info(f"Looking up ASN for {len(unique_ips)} unique IPs")

        # Single tracked entry for the whole batch
        self.logger.tool_start('asn_lookup', f'{len(unique_ips)} IPs')
        asn_map = {}
        tasks = []
        for ip in unique_ips:
            url = ASN_API_URL.format(ip=ip)
            tasks.append(self.runner.fetch_url(url, tool_name='asn_lookup'))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        found = 0
        for ip, result in zip(unique_ips, results):
            if isinstance(result, Exception):
                continue
            if isinstance(result, dict) and result.get('success'):
                try:
                    data = json.loads(result.get('body', '{}'))
                    org = data.get('org', '')
                    if org and org.startswith('AS'):
                        asn_map[ip] = org
                        found += 1
                except (json.JSONDecodeError, ValueError):
                    pass

        # Merge ASN info back into info_map
        for host, info in info_map.items():
            ip = info.get('ip')
            if ip and ip in asn_map:
                info['asn'] = asn_map[ip]

        self.logger.tool_end('asn_lookup', None, found)
    
    def parse_output(self, raw: str) -> List[Any]:
        """Parse raw output into Subdomain objects."""
        data = json.loads(raw)
        return [Subdomain(**item) for item in data]
