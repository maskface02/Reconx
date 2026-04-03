# reconx Configuration Guide

## Overview

The `config.yaml` file controls everything about how reconx performs reconnaissance and exploitation. The target, scope, performance settings, and API keys are all defined here — **no CLI target flags needed**.

## Critical Concept: Config Is the Single Source of Truth

**Important:** The `target:` value in config.yaml is the **only** way to specify what to scan.

```bash
# Config file says:
target: example.com

# Just run:
python3 main.py run

# Result: Target is 'example.com' from config
```

To scan a different target, simply edit `config.yaml` or use `--config` with an alternate file.

---

## Configuration Sections

### 1. Target & Scope

#### `target` (Required)
```yaml
target: example.com
```
- **Purpose:** The domain to test
- **Must be set:** Pipeline will refuse to run without it
- **Recommendation:** Set to your engagement target

#### `scope` (Inclusion List)
```yaml
scope:
  - "*.example.com"
  - "example.com"
```

**How it works:**
- Defines which subdomains are **allowed** in results
- Wildcards supported: `*.domain.com` matches `api.domain.com`, `test.domain.com`
- **Empty list `[]`** = Accept everything (no filtering)
- **Best practice:** Use wildcards matching your target domain

**Examples:**
```yaml
# Strict - only specific subdomains
scope:
  - "api.example.com"
  - "app.example.com"

# Standard - domain and all subdomains
scope:
  - "*.example.com"
  - "example.com"

# Empty - accept all (aggressive scanning)
scope: []
```

#### `exclude` (Blacklist)
```yaml
exclude:
  - "out-of-scope.example.com"
  - "*.prod.example.com"
```

**How it works:**
- Checked **before** scope (highest priority)
- Matched items are **immediately rejected**
- Use for production systems, sensitive areas, or out-of-scope assets
- Supports wildcards like `*.prod.*`

**Filter Order:**
1. Check `exclude` → Reject if match
2. Check `scope` → Accept if match (or if scope empty)
3. Reject if no scope match

---

### 2. Performance Settings

```yaml
rate_limit: 50          # Global requests per second
threads: 20             # Parallel operations
```

**Timeout is managed internally by the framework:**
- Default: **300 seconds** for all tool execution
- Phase 1 tools (subfinder, amass): **300 seconds** (dedicated runners)
- HTTP API calls (crt.sh, chaos): **30 seconds**
- No config needed — the framework handles this automatically

**Adjust based on target:**
```yaml
# Aggressive (fast network, robust target)
rate_limit: 100
threads: 50

# Conservative (slow network, WAF present, fragile target)
rate_limit: 10
threads: 5
```

---

### 3. Wordlists

```yaml
wordlist_dirs: /usr/share/seclists/Discovery/Web-Content/
wordlist_subs: /usr/share/seclists/Discovery/DNS/
```

**Purpose:**
- Directory brute-forcing (ffuf, feroxbuster)
- Subdomain enumeration (if tools support custom wordlists)
- Parameter discovery

**If paths wrong:** Tools fall back to defaults or skip.

---

### 4. Tool Paths

```yaml
tools:
  subfinder: /usr/local/bin/subfinder
  nuclei: /usr/local/bin/nuclei
  sqlmap: /usr/local/bin/sqlmap
  # ... etc
```

**How it works:**
- **Empty value or omitted:** Uses system `PATH`
- **Full path:** Uses specified binary
- **Purpose:** Useful for custom installations or multiple tool versions

**Example - mixed setup:**
```yaml
tools:
  # System PATH (default)
  subfinder: subfinder
  nuclei: nuclei

  # Custom paths
  sqlmap: /opt/sqlmap/sqlmap.py
  nuclei: /root/tools/nuclei
```

---

### 5. Nuclei Templates

```yaml
nuclei_templates: /usr/share/nuclei-templates/
```

**Purpose:**
- Path to nuclei vulnerability templates
- Used in Phase 5 (Scanning) and Phase 6 (CVE exploitation)
- Default: `/usr/share/nuclei-templates/`

**To update templates:**
```bash
nuclei -update-templates
```

---

### 6. Optional Integrations

#### Chaos API (Subdomain Discovery)
```yaml
chaos_api_key: "your-api-key-here"
```
- ProjectDiscovery Chaos dataset access
- Used in Phase 1 for additional subdomain discovery
- Get key at: https://chaos.projectdiscovery.io

#### GitHub Token (Secret Discovery)
```yaml
github_token: "ghp_xxxxxxxxxxxx"
```
- Used by gitdorker in Phase 5
- Searches GitHub for leaked credentials related to target
- Needs `repo` and `read:org` scopes

#### Interact.sh (Blind SSRF Detection)
```yaml
interactsh_server: "your-interactsh-server.com"
```
- Callback server for blind SSRF testing in Phase 6
- Default: "" (disabled)
- Set up your own: https://github.com/projectdiscovery/interactsh

---

## Practical Configuration Examples

### Example 1: Standard Config
```yaml
# config.yaml
target: example.com
scope:
  - "*.example.com"
  - "example.com"
exclude: []

rate_limit: 50
threads: 20

wordlist_dirs: /usr/share/seclists/Discovery/Web-Content/
wordlist_subs: /usr/share/seclists/Discovery/DNS/

tools:
  subfinder: subfinder
  amass: amass
  httpx: httpx
  # ... (list all tools)

nuclei_templates: /usr/share/nuclei-templates/

# Optional API keys
chaos_api_key: ""
github_token: ""
interactsh_server: ""
```

**Usage:**
```bash
python3 main.py run
```

---

### Example 2: Target-Specific Config
Strict scope for specific engagement:

```yaml
# apple-config.yaml
target: apple.com
scope:
  - "developer.apple.com"
  - "*.developer.apple.com"
  - "support.apple.com"
exclude:
  - "secure1.apple.com"     # Sensitive
  - "secure2.apple.com"
  - "*.prod.apple.com"      # Production

rate_limit: 20              # Gentle on specific targets
threads: 10
```

**Usage:**
```bash
python3 main.py run --config apple-config.yaml
```

---

### Example 3: Aggressive Internal Scanning
Fast scanning for internal/CICD use:

```yaml
target: internal.company.com
scope:
  - "*.internal.company.com"
  - "internal.company.com"
exclude: []

rate_limit: 200             # High speed (internal network)
threads: 100

# All tools explicitly pathed for Docker/CI
tools:
  subfinder: /usr/local/bin/subfinder
  nuclei: /usr/local/bin/nuclei
  # ... all tools
```

---

### Example 4: Stealth/WAF Evasion
When targeting WAF-protected sites:

```yaml
target: protected-site.com
scope: []
exclude: []

rate_limit: 5               # Very slow (evade rate limiting)
threads: 2

# No API keys - passive only
chaos_api_key: ""
github_token: ""
interactsh_server: ""
```

---

## Common Pitfalls

### Pitfall 1: Wrong Scope
```yaml
# config.yaml
target: apple.com
scope:
  - "*.example.com"
```

**Problem:** Scope checks for `*.example.com`, so `*.apple.com` subdomains will be **rejected**!

**Solution:** Ensure `scope` patterns match your `target` domain, or use `scope: []` to accept all.

---

### Pitfall 2: Missing Tool Paths
```yaml
tools:
  subfinder: ""    # Empty
```

**Result:** Framework tries to run empty command, fails.

**Solution:** Omit tool entirely to use PATH, or provide full path.

---

### Pitfall 3: Rate Limit Too High
```yaml
rate_limit: 1000
```

**Result:** Target blocks you, WAF bans IP, or tools crash.

**Solution:** Start conservative (20-50), increase based on target response.

---

### Pitfall 4: Wrong Wordlist Paths
```yaml
wordlist_dirs: /usr/share/wordlists/   # Missing specific subdir
```

**Result:** ffuf/feroxbuster fail to find wordlists.

**Solution:** Verify paths exist:
```bash
ls /usr/share/seclists/Discovery/Web-Content/
```

---

## Configuration Validation Checklist

Before running:

- [ ] `target` is set to your engagement domain
- [ ] `scope` is empty `[]` OR matches your target domain
- [ ] `exclude` contains any sensitive/out-of-scope subdomains
- [ ] `rate_limit` appropriate for target (production = low, internal = high)
- [ ] `tools` paths are correct or omitted (to use PATH)
- [ ] `wordlist_dirs` exists and contains wordlist files
- [ ] `nuclei_templates` exists (run `nuclei -update-templates`)
- [ ] API keys filled in if using Chaos/GitDorker features

---

## Command-Line Reference

| Command | Description |
|---------|-------------|
| `python3 main.py run` | Run full pipeline (reads config) |
| `python3 main.py run --phase 1` | Run single phase |
| `python3 main.py run --from-phase 3` | Resume from phase 3 |
| `python3 main.py run --force` | Force re-run all phases |
| `python3 main.py run --config alt.yaml` | Use alternate config |
| `python3 main.py review` | Open review TUI |
| `python3 main.py report` | Generate markdown report |
| `python3 main.py report --format html` | Generate HTML report |
| `python3 main.py status` | Show workspace status |
| `python3 main.py clear` | Clear workspace |
| `python3 main.py init` | Create config template |

| Setting | CLI Flag | Config File | Winner |
|---------|----------|-------------|---------|
| Target | N/A | `target:` | **Config** |
| Config path | `--config` | N/A | **CLI** |
| Phase control | `--phase`, `--from-phase` | N/A | **CLI** |
| Force re-run | `--force` | N/A | **CLI** |
| Rate limit | N/A | `rate_limit:` | **Config** |
| Scope | N/A | `scope:` | **Config** |
| Exclude | N/A | `exclude:` | **Config** |
| Tool paths | N/A | `tools:` | **Config** |
| API keys | N/A | `chaos_api_key:` etc | **Config** |
| Timeout | N/A | Managed internally | **Framework** |

---

## Quick Reference

### Minimal Working Config
```yaml
target: example.com
scope: []
exclude: []
rate_limit: 50
threads: 20
tools: {}
```

### Full Production Config
```yaml
target: company.com
scope:
  - "*.company.com"
  - "company.com"
exclude:
  - "prod.company.com"
  - "admin.company.com"

rate_limit: 20
threads: 10

wordlist_dirs: /usr/share/seclists/Discovery/Web-Content/
wordlist_subs: /usr/share/seclists/Discovery/DNS/

tools:
  subfinder: subfinder
  amass: amass
  dnsx: dnsx
  httpx: httpx
  katana: katana
  ffuf: ffuf
  feroxbuster: feroxbuster
  paramspider: paramspider
  arjun: arjun
  nuclei: nuclei
  sqlmap: sqlmap
  dalfox: dalfox
  gf: gf
  secretfinder: secretfinder
  trufflehog: trufflehog
  wafw00f: wafw00f
  masscan: masscan
  nmap: nmap
  nikto: nikto
  waybackurls: waybackurls
  gau: gau
  gospider: gospider
  hakrawler: hakrawler
  linkfinder: linkfinder
  x8: x8
  xsstrike: xsstrike
  jwt_tool: jwt-tool
  gitdorker: gitdorker
  ghauri: ghauri

nuclei_templates: /usr/share/nuclei-templates/
interactsh_server: ""
github_token: ""
chaos_api_key: ""
```

---

## Summary

1. **`target:` is required** — it's the single source of truth for what to scan
2. **`scope: []`** for universal scanning, or match your target domain
3. **`exclude` is checked first** — use to protect sensitive systems
4. **`rate_limit` controls politeness** — adjust for production vs internal
5. **Tool paths are optional** — omit to use system PATH
6. **Timeout is managed internally** — 300s default, no config needed
7. **Use `--config`** to switch between different target configs
