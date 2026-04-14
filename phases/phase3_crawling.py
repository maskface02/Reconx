"""
Phase 3: URL & Endpoint Crawling
Discover every URL, endpoint, JS file, form, and API path.
"""
import json
import asyncio
from typing import List, Any, Set, Dict
from pathlib import Path
from urllib.parse import urlparse, urljoin

from core.workspace import Workspace
from core.models import CrawledUrl, PhaseOutput
from core.utils import deduplicate_lines, is_in_scope
from .base import BasePhase, PhaseException


class Phase3Crawling(BasePhase):
    """Phase 3: URL and endpoint crawling."""

    name = "URL & Endpoint Crawling"
    phase_number = 3
    input_file = "urls.txt"
    output_file = "phase3_output.json"

    def __init__(self, workspace: Workspace, config: dict):
        super().__init__(workspace, config)
        self.target = config['target']
        self.scope = config.get('scope', [f"*.{self.target}", self.target])
        self.exclude = config.get('exclude', [])

    async def run(self) -> PhaseOutput:
        """Execute Phase 3: URL crawling."""
        self.logger.phase_start(self.name, target=self.target)

        # Load URLs from Phase 2
        urls_file = self.workspace.workspace_path / "urls.txt"
        if not urls_file.exists():
            error_msg = (
                f"Phase 2 output not found (urls.txt). "
                f"Phase 3 requires Phase 2 to complete first. "
                f"Run: python3 main.py run --phase 2"
            )
            self.logger.error(error_msg)
            raise PhaseException(error_msg)

        urls = self.workspace.load_text_file("urls.txt")
        if not urls:
            self.logger.warning("urls.txt is empty, Phase 2 found no live URLs")
            # Save empty output so phase is marked as completed
            self.workspace.save_phase_output(3, [])
            return PhaseOutput(
                phase=self.name,
                count=0,
                output_file=str(self.workspace.get_phase_output(3))
            )

        self.logger.info(f"Crawling {len(urls)} URLs")

        all_urls: Set[str] = set()
        js_files: Set[str] = set()

        # Run crawlers in parallel
        tasks = []

        # Katana
        if self.tool_available('katana'):
            for url in urls[:5]:  # Limit to avoid overwhelming
                tasks.append(self._run_katana(url))
        else:
            self.logger.tool_skipped('katana', 'not installed')

        # Gospider
        if self.tool_available('gospider'):
            for url in urls[:5]:
                tasks.append(self._run_gospider(url))
        else:
            self.logger.tool_skipped('gospider', 'not installed')

        # Hakrawler
        if self.tool_available('hakrawler'):
            for url in urls[:5]:
                tasks.append(self._run_hakrawler(url))
        else:
            self.logger.tool_skipped('hakrawler', 'not installed')

        # Waybackurls
        if self.tool_available('waybackurls'):
            tasks.append(self._run_waybackurls())
        else:
            self.logger.tool_skipped('waybackurls', 'not installed')

        # GAU
        if self.tool_available('gau'):
            tasks.append(self._run_gau())
        else:
            self.logger.tool_skipped('gau', 'not installed')

        # Wait for all crawling tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Crawling task failed: {result}")
                continue
            for url in result:
                if is_in_scope(url, self.scope, self.exclude):
                    all_urls.add(url)
                    # Classify JS files
                    if url.endswith('.js') or '.js?' in url:
                        js_files.add(url)

        self.logger.info(f"Discovered {len(all_urls)} unique URLs, {len(js_files)} JS files")

        # Run LinkFinder on JS files
        if js_files and self.tool_available('linkfinder'):
            await self._run_linkfinder(js_files)

        # Filter and classify URLs
        classified = self._classify_urls(all_urls)

        # Create CrawledUrl objects
        crawled_urls = []
        for url in all_urls:
            crawled_urls.append(CrawledUrl(
                url=url,
                source="crawler",
                method="GET"
            ))

        # Save outputs
        output_data = [c.model_dump() for c in crawled_urls]
        self.workspace.save_phase_output(3, output_data)

        # Save flat files
        self.workspace.save_text_file("all_urls.txt", sorted(all_urls))
        self.workspace.save_text_file("js_files.txt", sorted(js_files))

        self.logger.phase_end(self.name, str(self.workspace.get_phase_output(3)), len(crawled_urls))

        return PhaseOutput(
            phase=self.name,
            count=len(crawled_urls),
            output_file=str(self.workspace.get_phase_output(3)),
            metadata={
                "js_files": len(js_files),
                "api_endpoints": len(classified.get('api_endpoints', [])),
                "forms": len(classified.get('forms', []))
            }
        )

    async def _run_katana(self, url: str) -> List[str]:
        """Run katana crawler."""
        output_file = self.workspace.get_raw_file(f"katana_{url.replace('://', '_').replace('/', '_')}.txt")

        cmd = [
            self.get_tool_path('katana'),
            '-u', url,
            '-headless',
            '-js-crawl',
            '-depth', '5',
            '-concurrency', '20',
            '-silent',
            '-o', str(output_file)
        ]

        result = await self.runner.run('katana', cmd, output_file)

        urls = []
        if result.success and output_file.exists():
            with open(output_file, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]

        return urls

    async def _run_gospider(self, url: str) -> List[str]:
        """Run gospider crawler."""
        output_dir = self.workspace.get_raw_file(f"gospider_{url.replace('://', '_').replace('/', '_')}")

        cmd = [
            self.get_tool_path('gospider'),
            '-s', url,
            '-o', str(output_dir),
            '-t', '20',
            '--depth', '5'
        ]

        result = await self.runner.run('gospider', cmd)

        urls = []
        if result.success and output_dir.exists():
            # Parse gospider output files
            for file in output_dir.glob('*.txt'):
                with open(file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and line.startswith('http'):
                            urls.append(line)

        return urls

    async def _run_hakrawler(self, url: str) -> List[str]:
        """Run hakrawler."""
        output_file = self.workspace.get_raw_file(f"hakrawler_{url.replace('://', '_').replace('/', '_')}.txt")

        cmd = [
            self.get_tool_path('hakrawler'),
            '-url', url,
            '-depth', '5',
            '-plain'
        ]

        result = await self.runner.run('hakrawler', cmd, output_file)

        urls = []
        if result.success:
            urls = [line.strip() for line in result.stdout.split('\n')
                    if line.strip() and line.strip().startswith('http')]
            with open(output_file, 'w') as f:
                f.write('\n'.join(urls))

        return urls

    async def _run_waybackurls(self) -> List[str]:
        """Run waybackurls for historical URLs."""
        output_file = self.workspace.get_raw_file("waybackurls.txt")

        cmd = [
            self.get_tool_path('waybackurls'),
            self.target
        ]

        result = await self.runner.run('waybackurls', cmd, output_file)

        urls = []
        if result.success:
            urls = [line.strip() for line in result.stdout.split('\n')
                    if line.strip() and line.strip().startswith('http')]
            with open(output_file, 'w') as f:
                f.write('\n'.join(urls))
            self.logger.tool_end('waybackurls', str(output_file), len(urls))

        return urls

    async def _run_gau(self) -> List[str]:
        """Run gau (GetAllUrls) for historical URLs."""
        output_file = self.workspace.get_raw_file("gau.txt")

        cmd = [
            self.get_tool_path('gau'),
            self.target
        ]

        result = await self.runner.run('gau', cmd, output_file)

        urls = []
        if result.success:
            urls = [line.strip() for line in result.stdout.split('\n')
                    if line.strip() and line.strip().startswith('http')]
            with open(output_file, 'w') as f:
                f.write('\n'.join(urls))
            self.logger.tool_end('gau', str(output_file), len(urls))

        return urls

    async def _run_linkfinder(self, js_files: Set[str]) -> None:
        """Run LinkFinder on JS files and combine endpoints with base URL."""
        all_endpoints = []

        for js_url in list(js_files)[:20]:  # Limit to avoid overwhelming
            cmd = [
                self.get_tool_path('linkfinder'),
                '-i', js_url,
                '-o', 'cli'
            ]

            result = await self.runner.run('linkfinder', cmd)

            if result.success:
                relative_paths = [line.strip() for line in result.stdout.split('\n') if line.strip()]

                # Extract base URL from the JS file URL
                parsed = urlparse(js_url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"

                # Combine relative paths with base URL to form full URLs
                for path in relative_paths:
                    if path.startswith('http'):
                        # Already an absolute URL (some JS files reference external APIs)
                        full_url = path
                    elif path.startswith('//'):
                        # Protocol-relative URL (e.g., "//api.example.com/users")
                        full_url = f"{parsed.scheme}:{path}"
                    elif path.startswith('/'):
                        # Absolute path (e.g., "/api/users")
                        full_url = urljoin(base_url, path)
                    else:
                        # Relative path (e.g., "api/users" or "../api/users")
                        # Resolve relative to the JS file's directory
                        js_dir = js_url.rsplit('/', 1)[0] if '/' in js_url else base_url
                        full_url = urljoin(js_dir + '/', path)

                    # Validate URL is in scope before adding
                    if is_in_scope(full_url, self.scope, self.exclude):
                        all_endpoints.append(full_url)

        # Save combined endpoints
        if all_endpoints:
            endpoints_file = self.workspace.get_raw_file("linkfinder_endpoints.txt")
            with open(endpoints_file, 'w') as f:
                f.write(''.join(sorted(set(all_endpoints))))  # Deduplicate and sort
            self.logger.tool_end('linkfinder', str(endpoints_file), len(set(all_endpoints)))

    def _classify_urls(self, urls: Set[str]) -> Dict[str, List[str]]:
        """Classify URLs by type."""
        classified = {
            'js_files': [],
            'api_endpoints': [],
            'forms': [],
            'other': []
        }

        for url in urls:
            parsed = urlparse(url)
            path = parsed.path.lower()

            if path.endswith('.js') or '.js?' in url:
                classified['js_files'].append(url)
            elif '/api/' in path:
                classified['api_endpoints'].append(url)
            elif any(param in url.lower() for param in ['?id=', '?page=', '?search=']):
                classified['forms'].append(url)
            else:
                classified['other'].append(url)

        return classified

    def parse_output(self, raw: str) -> List[Any]:
        """Parse raw output into CrawledUrl objects."""
        data = json.loads(raw)
        return [CrawledUrl(**item) for item in data]
