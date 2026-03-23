"""
Utility functions for reconx framework.
"""
import re
import hashlib
from urllib.parse import urlparse
from typing import List, Set, Dict, Any, Optional
from pathlib import Path


def is_in_scope(url: str, scope: List[str], exclude: List[str]) -> bool:
    """
    Check if a URL is within the defined scope.
    
    Args:
        url: The URL to check
        scope: List of scope patterns (e.g., "*.example.com", "example.com")
        exclude: List of exclusion patterns
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or url
    
    # Check exclusions first
    for pattern in exclude:
        if _matches_pattern(hostname, pattern):
            return False
    
    # Check scope
    if not scope:
        return True
    
    for pattern in scope:
        if _matches_pattern(hostname, pattern):
            return True
    
    return False


def _matches_pattern(hostname: str, pattern: str) -> bool:
    """Check if hostname matches a pattern."""
    pattern = pattern.strip()
    
    # Wildcard pattern
    if pattern.startswith("*."):
        domain = pattern[2:]
        return hostname == domain or hostname.endswith("." + domain)
    
    # Exact match
    return hostname == pattern


def deduplicate_lines(lines: List[str]) -> List[str]:
    """Deduplicate a list of lines while preserving order."""
    seen: Set[str] = set()
    result: List[str] = []
    for line in lines:
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            result.append(line)
    return result


def merge_jsonl_files(files: List[Path]) -> List[Dict[str, Any]]:
    """Merge multiple JSONL files into a list of dicts."""
    results = []
    for file in files:
        if file.exists():
            with open(file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            import json
                            results.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
    return results


def hash_content(content: str) -> str:
    """Create a hash of content for comparison."""
    return hashlib.md5(content.encode()).hexdigest()


def differs_from_baseline(
    url: str, 
    response_snippet: str, 
    baseline: Optional[Dict[str, Any]],
    threshold: float = 0.8
) -> bool:
    """
    Check if a response differs significantly from baseline.
    
    Args:
        url: The URL being checked
        response_snippet: Current response snippet
        baseline: Baseline response data
        threshold: Similarity threshold (0-1, higher = more similar)
    
    Returns:
        True if response differs from baseline
    """
    if not baseline:
        return True
    
    baseline_body = baseline.get("body", "")
    if not baseline_body:
        return True
    
    # Simple content length comparison
    baseline_length = len(baseline_body)
    current_length = len(response_snippet)
    
    # If lengths differ significantly, responses differ
    if baseline_length > 0:
        length_ratio = min(current_length, baseline_length) / max(current_length, baseline_length)
        if length_ratio < threshold:
            return True
    
    # Hash comparison for exact match
    baseline_hash = hash_content(baseline_body[:1000])
    current_hash = hash_content(response_snippet[:1000])
    
    return baseline_hash != current_hash


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.hostname or url


def extract_path(url: str) -> str:
    """Extract path from URL."""
    parsed = urlparse(url)
    return parsed.path or "/"


def normalize_url(url: str) -> str:
    """Normalize URL for comparison."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.hostname}{parsed.path}".rstrip('/')


def parse_subfinder_output(output: str) -> List[str]:
    """Parse subfinder output into list of subdomains."""
    return [line.strip() for line in output.split('\n') if line.strip()]


def parse_amass_output(output: str) -> List[str]:
    """Parse amass output into list of subdomains."""
    subdomains = []
    for line in output.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            # Amass can output in various formats, extract domain
            parts = line.split()
            for part in parts:
                if '.' in part and not part.startswith('http'):
                    subdomains.append(part)
                    break
    return subdomains


def parse_httpx_jsonl(output: str) -> List[Dict[str, Any]]:
    """Parse httpx JSONL output."""
    results = []
    for line in output.split('\n'):
        line = line.strip()
        if line:
            try:
                import json
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return results


def parse_nuclei_jsonl(output: str) -> List[Dict[str, Any]]:
    """Parse nuclei JSONL output."""
    return parse_httpx_jsonl(output)  # Same format


def parse_crtsh_json(output: str) -> List[str]:
    """Parse crt.sh JSON output."""
    subdomains = []
    try:
        import json
        data = json.loads(output)
        for entry in data:
            name = entry.get('name_value', '')
            if name:
                # Handle multi-line entries
                for sub in name.split('\n'):
                    sub = sub.strip()
                    if sub and '*' not in sub:
                        subdomains.append(sub)
    except json.JSONDecodeError:
        pass
    return subdomains


def is_generic_template(template: Optional[str]) -> bool:
    """Check if a nuclei template is considered generic/noisy."""
    if not template:
        return False
    
    generic_patterns = [
        'tech-detect',
        'favicon',
        'robots',
        'sitemap',
        'readme',
        'changelog',
        'license'
    ]
    
    template_lower = template.lower()
    return any(pattern in template_lower for pattern in generic_patterns)


def redact_secrets(text: str, secret_patterns: Optional[List[str]] = None) -> str:
    """Redact potential secrets from text."""
    if secret_patterns is None:
        secret_patterns = [
            (r'[Aa][Ww][Ss][_\-]?[Aa][Cc][Cc][Ee][Ss][Ss][_\-]?[Kk][Ee][Yy][_\-]?[A-Za-z0-9]{20}', 'AWS_ACCESS_KEY_***'),
            (r'[Aa][Ww][Ss][_\-]?[Ss][Ee][Cc][Rr][Ee][Tt][_\-]?[A-Za-z0-9/+=]{40}', 'AWS_SECRET_***'),
            (r'[Gg][Hh][Pp]_[A-Za-z0-9]{36}', 'ghp_***'),
            (r'[Gg][Ii][Tt][Hh][Uu][Bb][_\-]?[Tt][Oo][Kk][Ee][Nn][\s]*[=:][\s]*[A-Za-z0-9]{35,40}', 'GITHUB_TOKEN=***'),
            (r'[Aa][Pp][Ii][_\-]?[Kk][Ee][Yy][\s]*[=:][\s]*[A-Za-z0-9]{16,64}', 'API_KEY=***'),
            (r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----', '-----BEGIN PRIVATE KEY-----***'),
        ]
    
    redacted = text
    for pattern, replacement in secret_patterns:
        redacted = re.sub(pattern, replacement, redacted)
    
    return redacted


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split a list into chunks."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def count_lines(filepath: Path) -> int:
    """Count lines in a file."""
    if not filepath.exists():
        return 0
    with open(filepath, 'r') as f:
        return sum(1 for _ in f)


def safe_json_load(filepath: Path, default: Any = None) -> Any:
    """Safely load JSON file with fallback default."""
    if default is None:
        default = []
    if not filepath.exists():
        return default
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


import json
