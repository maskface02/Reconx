"""
Phase 4: Directory Enumeration & Parameter Discovery
Brute-force hidden paths and discover injectable parameters.
"""
import json
import asyncio
from typing import List, Any, Dict, Set
from pathlib import Path
from urllib.parse import urlparse

from core.workspace import Workspace
from core.models import Parameter, PhaseOutput
from core.utils import deduplicate_lines, is_in_scope
from .base import BasePhase, PhaseException


class Phase4Enumeration(BasePhase):
    """Phase 4: Directory enumeration and parameter discovery."""
    
    name = "Directory Enumeration & Parameter Discovery"
    phase_number = 4
    input_file = "all_urls.txt"
    output_file = "phase4_output.json"
    
    def __init__(self, workspace: Workspace, config: dict):
        super().__init__(workspace, config)
        self.target = config['target']
        self.scope = config.get('scope', [f"*.{self.target}", self.target])
        self.exclude = config.get('exclude', [])
        self.wordlist_dirs = config.get('wordlist_dirs', '/usr/share/wordlists/')
    
    async def run(self) -> PhaseOutput:
        """Execute Phase 4: Enumeration."""
        self.logger.phase_start(self.name, target=self.target)

        # Load URLs from Phase 3
        urls_file = self.workspace.workspace_path / "all_urls.txt"
        if not urls_file.exists():
            error_msg = (
                f"Phase 3 output not found (all_urls.txt). "
                f"Phase 4 requires Phase 3 to complete first. "
                f"Run: python3 main.py run --phase 3"
            )
            self.logger.error(error_msg)
            raise PhaseException(error_msg)

        urls = self.workspace.load_text_file("all_urls.txt")
        if not urls:
            self.logger.warning("all_urls.txt is empty, Phase 3 found no URLs to crawl")
            # Save empty output so phase is marked as completed
            self.workspace.save_phase_output(4, [])
            return PhaseOutput(
                phase=self.name,
                count=0,
                output_file=str(self.workspace.get_phase_output(4))
            )
        
        # Get base URLs for directory enumeration
        base_urls = self._get_base_urls(urls)
        
        # Run 4a and 4b in parallel
        dir_task = self._enumerate_directories(base_urls)
        param_task = self._discover_parameters(urls)
        
        dirs, params = await asyncio.gather(dir_task, param_task)
        
        self.logger.info(f"Discovered {len(dirs)} directories and {len(params)} parameters")
        
        # Run gf pattern matching
        await self._run_gf_patterns()
        
        # Save outputs
        output_data = [p.model_dump() for p in params]
        self.workspace.save_phase_output(4, output_data)
        
        # Save flat files
        self.workspace.save_text_file("dirs.txt", sorted(dirs))
        
        self.logger.phase_end(self.name, str(self.workspace.get_phase_output(4)), len(params))
        
        return PhaseOutput(
            phase=self.name,
            count=len(params),
            output_file=str(self.workspace.get_phase_output(4)),
            metadata={"directories": len(dirs), "parameters": len(params)}
        )
    
    def _get_base_urls(self, urls: List[str]) -> List[str]:
        """Extract unique base URLs for directory enumeration."""
        base_urls = set()
        for url in urls:
            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            base_urls.add(base)
        return list(base_urls)
    
    async def _enumerate_directories(self, base_urls: List[str]) -> Set[str]:
        """4a: Enumerate directories using ffuf and feroxbuster."""
        all_dirs: Set[str] = set()
        
        # Find wordlist
        wordlist = self._find_wordlist()
        if not wordlist:
            self.logger.warning("No wordlist found for directory enumeration")
            return all_dirs
        
        # Run ffuf on each base URL
        if self.tool_available('ffuf'):
            for url in base_urls[:10]:  # Limit to avoid overwhelming
                dirs = await self._run_ffuf(url, wordlist)
                all_dirs.update(dirs)
        else:
            self.logger.tool_skipped('ffuf', 'not installed')
        
        # Run feroxbuster as secondary
        if self.tool_available('feroxbuster'):
            for url in base_urls[:5]:  # Limit
                dirs = await self._run_feroxbuster(url, wordlist)
                all_dirs.update(dirs)
        else:
            self.logger.tool_skipped('feroxbuster', 'not installed')
        
        return all_dirs
    
    def _find_wordlist(self) -> Path:
        """Find a suitable wordlist for directory enumeration."""
        common_paths = [
            Path(self.wordlist_dirs) / "common.txt",
            Path(self.wordlist_dirs) / "raft-small-directories.txt",
            Path("/usr/share/wordlists/dirb/common.txt"),
            Path("/usr/share/wordlists/dirbuster/directory-list-2.3-small.txt"),
            Path("/usr/share/seclists/Discovery/Web-Content/common.txt"),
        ]
        
        for path in common_paths:
            if path.exists():
                return path
        
        return None
    
    async def _run_ffuf(self, url: str, wordlist: Path) -> Set[str]:
        """Run ffuf for directory enumeration."""
        output_file = self.workspace.get_raw_file(f"ffuf_{url.replace('://', '_').replace('/', '_')}.json")
        
        cmd = [
            self.get_tool_path('ffuf'),
            '-u', f"{url}/FUZZ",
            '-w', str(wordlist),
            '-t', '40',
            '-mc', '200,301,302,403,405',
            '-o', str(output_file),
            '-of', 'json'
        ]
        
        result = await self.runner.run('ffuf', cmd, output_file)
        
        dirs = set()
        if result.success and output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    data = json.load(f)
                    for entry in data.get('results', []):
                        path = entry.get('input', {}).get('FUZZ', '')
                        if path:
                            dirs.add(f"{url}/{path}")
            except json.JSONDecodeError:
                pass
        
        return dirs
    
    async def _run_feroxbuster(self, url: str, wordlist: Path) -> Set[str]:
        """Run feroxbuster for directory enumeration."""
        output_file = self.workspace.get_raw_file(f"ferox_{url.replace('://', '_').replace('/', '_')}.json")
        
        cmd = [
            self.get_tool_path('feroxbuster'),
            '-u', url,
            '-w', str(wordlist),
            '-t', '20',
            '--json',
            '-o', str(output_file)
        ]
        
        result = await self.runner.run('feroxbuster', cmd, output_file)
        
        dirs = set()
        if result.success and output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line.strip())
                            path = data.get('url', '')
                            if path:
                                dirs.add(path)
            except json.JSONDecodeError:
                pass
        
        return dirs
    
    async def _discover_parameters(self, urls: List[str]) -> List[Parameter]:
        """4b: Discover parameters using various tools."""
        all_params: List[Parameter] = []
        
        # ParamSpider
        if self.tool_available('paramspider'):
            params = await self._run_paramspider()
            all_params.extend(params)
        else:
            self.logger.tool_skipped('paramspider', 'not installed')
        
        # Arjun on sampled URLs
        if self.tool_available('arjun'):
            sampled_urls = urls[:20] if len(urls) > 20 else urls
            for url in sampled_urls:
                params = await self._run_arjun(url)
                all_params.extend(params)
        else:
            self.logger.tool_skipped('arjun', 'not installed')
        
        # x8 parameter discovery
        if self.tool_available('x8'):
            sampled_urls = urls[:10] if len(urls) > 10 else urls
            for url in sampled_urls:
                params = await self._run_x8(url)
                all_params.extend(params)
        else:
            self.logger.tool_skipped('x8', 'not installed')
        
        return all_params
    
    async def _run_paramspider(self) -> List[Parameter]:
        """Run ParamSpider for parameter discovery."""
        output_file = self.workspace.get_raw_file("paramspider_out.txt")
        output_dir = self.workspace.get_raw_file("paramspider_output")
        
        cmd = [
            self.get_tool_path('paramspider'),
            '-d', self.target,
            '-o', str(output_dir)
        ]
        
        result = await self.runner.run('paramspider', cmd)
        
        params = []
        if result.success:
            # Parse paramspider output
            for file in output_dir.glob('*.txt'):
                with open(file, 'r') as f:
                    for line in f:
                        url = line.strip()
                        if url and '?' in url:
                            parsed = urlparse(url)
                            query_params = parsed.query.split('&')
                            for qp in query_params:
                                if '=' in qp:
                                    param_name = qp.split('=')[0]
                                    params.append(Parameter(
                                        url=url.split('?')[0],
                                        param=param_name,
                                        method="GET"
                                    ))
        
        return params
    
    async def _run_arjun(self, url: str) -> List[Parameter]:
        """Run Arjun for parameter discovery."""
        output_file = self.workspace.get_raw_file(f"arjun_{url.replace('://', '_').replace('/', '_')}.json")
        
        cmd = [
            self.get_tool_path('arjun'),
            '-u', url,
            '-oJ', str(output_file)
        ]
        
        result = await self.runner.run('arjun', cmd, output_file)
        
        params = []
        if result.success and output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    data = json.load(f)
                    for entry in data.get('params', []):
                        params.append(Parameter(
                            url=url,
                            param=entry.get('name', ''),
                            method=entry.get('method', 'GET')
                        ))
            except json.JSONDecodeError:
                pass
        
        return params
    
    async def _run_x8(self, url: str) -> List[Parameter]:
        """Run x8 for parameter discovery."""
        output_file = self.workspace.get_raw_file(f"x8_{url.replace('://', '_').replace('/', '_')}.json")
        
        # Find params wordlist
        wordlist = Path(self.wordlist_dirs) / "parameters.txt"
        if not wordlist or not wordlist.exists():
            wordlist = Path("/usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt")
        
        if not wordlist.exists():
            return []
        
        cmd = [
            self.get_tool_path('x8'),
            '-u', url,
            '-w', str(wordlist),
            '-o', str(output_file)
        ]
        
        result = await self.runner.run('x8', cmd, output_file)
        
        params = []
        if result.success and output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    data = json.load(f)
                    for entry in data:
                        params.append(Parameter(
                            url=url,
                            param=entry.get('parameter', ''),
                            method=entry.get('method', 'GET')
                        ))
            except json.JSONDecodeError:
                pass
        
        return params
    
    async def _run_gf_patterns(self) -> None:
        """Run gf pattern matching on discovered URLs."""
        if not self.tool_available('gf'):
            self.logger.tool_skipped('gf', 'not installed')
            return
        
        all_urls_file = self.workspace.workspace_path / "all_urls.txt"
        gf_patterns_path = self.workspace.gf_patterns_path
        
        patterns = ['xss', 'sqli', 'ssrf', 'redirect', 'lfi']
        
        for pattern in patterns:
            output_file = gf_patterns_path / f"{pattern}.txt"
            
            cmd = [
                self.get_tool_path('gf'),
                pattern,
                str(all_urls_file)
            ]
            
            result = await self.runner.run('gf', cmd, output_file)
            
            if result.success:
                self.logger.tool_end(f'gf_{pattern}', str(output_file))
    
    def parse_output(self, raw: str) -> List[Any]:
        """Parse raw output into Parameter objects."""
        data = json.loads(raw)
        return [Parameter(**item) for item in data]
