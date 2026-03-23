# reconx Configuration Guide

## Overview

The `config.yaml` file controls how reconx performs reconnaissance and exploitation. While the CLI `--target` argument specifies **what** to scan, the config file controls **how** to scan it.

## Critical Concept: CLI Target Overrides Config

**Important:** The `--target` CLI argument **always takes precedence** over the `target:` value in config.yaml.

```bash
# Config file says:
target: example.com

# But you run:
python3 main.py run --target apple.com --config config.yaml

# Result: Target becomes 'apple.com', config target is ignored
```

This design allows you to **reuse one config file** for multiple targets.

---

## Configuration Sections

### 1. Target & Scope

#### `target` (Optional)
```yaml
target: example.com
```
- **Purpose:** Default/fallback target
- **Override:** CLI `--target` argument always wins
- **Recommendation:** Set as placeholder or remove entirely

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
- **Best practice:** Leave empty if using CLI `--target` for flexibility

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

# Empty - accept all (recommended for CLI usage)
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
timeout: 10             # Seconds per HTTP request/tool execution
```

**Adjust based on target:**
```yaml
# Aggressive (fast network, robust target)
rate_limit: 100
threads: 50
timeout: 5

# Conservative (slow network, WAF present, fragile target)
rate_limit: 10
threads: 5
timeout: 30
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

### Example 1: Universal Config (Recommended)
Reuse for any target without editing:

```yaml
# config.yaml
target: placeholder.com    # Ignored - use CLI --target
scope: []                  # Accept all
exclude: []                # Nothing excluded

rate_limit: 50
threads: 20
timeout: 10

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
python3 main.py run --target apple.com --config config.yaml
python3 main.py run --target google.com --config config.yaml
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
# Note: --target apple.com optional here since it's in config
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
timeout: 5                  # Fast timeout

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
timeout: 30                 # Long timeouts

# No API keys - passive only
chaos_api_key: ""
github_token: ""
interactsh_server: ""
```

---

## Common Pitfalls

### Pitfall 1: Scope/CLI Mismatch
```yaml
# config.yaml
target: example.com
scope:
  - "*.example.com"
```

```bash
python3 main.py run --target apple.com --config config.yaml
```

**Problem:** Scope still checks for `*.example.com`, so `*.apple.com` subdomains will be **rejected**!

**Solution:** Use `scope: []` for CLI flexibility, or ensure scope patterns match your CLI target.

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

- [ ] `scope` is empty `[]` OR matches your CLI `--target` domain
- [ ] `exclude` contains any sensitive/out-of-scope subdomains
- [ ] `rate_limit` appropriate for target (production = low, internal = high)
- [ ] `tools` paths are correct or omitted (to use PATH)
- [ ] `wordlist_dirs` exists and contains wordlist files
- [ ] `nuclei_templates` exists (run `nuclei -update-templates`)
- [ ] API keys filled in if using Chaos/GitDorker features

---

## Command-Line vs Config Priority

| Setting | CLI Flag | Config File | Winner |
|---------|----------|-------------|---------|
| Target | `--target` | `target:` | **CLI** |
| Config path | `--config` | N/A | **CLI** |
| Phase control | `--phase`, `--from-phase` | N/A | **CLI** |
| Force re-run | `--force` | N/A | **CLI** |
| Rate limit | N/A | `rate_limit:` | **Config** |
| Scope | N/A | `scope:` | **Config** |
| Exclude | N/A | `exclude:` | **Config** |
| Tool paths | N/A | `tools:` | **Config** |
| API keys | N/A | `chaos_api_key:` etc | **Config** |

---

## Quick Reference

### Minimal Working Config
```yaml
target: example.com
scope: []
exclude: []
rate_limit: 50
threads: 20
timeout: 10
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
timeout: 15

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
  ssrfire: ssrfire
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

1. **Use `scope: []`** for universal configs that work with any `--target`
2. **CLI `--target` overrides** config `target:`
3. **`exclude` is checked first** - use to protect sensitive systems
4. **`rate_limit` controls politeness** - adjust for production vs internal
5. **Tool paths are optional** - omit to use system PATH
6. **Keep one master config** and reuse for multiple targets via CLI arguments
