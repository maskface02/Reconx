# 🔍 reconx - Modular Penetration Testing Framework

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Asyncio](https://img.shields.io/badge/asyncio-supported-green.svg)](https://docs.python.org/3/library/asyncio.html)

> **reconx** is a comprehensive, CLI-driven penetration testing framework that automates the full reconnaissance-to-exploitation pipeline with intelligent false-positive filtering.

## 🌟 Key Features

- **6-Phase Pipeline**: Complete workflow from subdomain discovery to targeted exploitation
- **Intelligent FP Filter**: Confidence-based scoring engine reduces noise by 60-80%
- **Async Architecture**: High-performance concurrent execution with rate limiting
- **Config-Driven**: Target and scope defined in config — no CLI flags needed
- **Resume Support**: Re-run skips completed phases (unless `--force`)
- **Manual Review TUI**: Interactive terminal UI for uncertain findings
- **Multi-Format Reports**: JSON, HTML, and Markdown output

## 🏗️ Architecture

```
Phase 1: Discovery     → subfinder, amass, assetfinder, crt.sh, chaos
    ↓
Phase 2: Probing       → httpx, masscan, nmap, wafw00f
    ↓
Phase 3: Crawling      → katana, gospider, waybackurls, linkfinder
    ↓
Phase 4: Enumeration   → ffuf, feroxbuster, paramspider, arjun, gf
    ↓
Phase 5: Scanning      → nuclei, secretfinder, trufflehog, nikto
    ↓
FP Filter              → Scoring engine routes findings
    ↓
Phase 6: Exploitation  → sqlmap, dalfox, jwt-tool
```

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/maskface02/reconx.git
cd reconx

# Install Python dependencies
pip3 install -r requirements.txt --break-system-packages

# Install external security tools
sudo bash setup_tools.sh
```

### Initialize & Run

```bash
# Create configuration template
python3 main.py init

# Edit config.yaml with your target and API keys
vim config.yaml

# Run full pipeline — reads target from config.yaml
python3 main.py run
```

## 📋 Usage Examples

### Run Pipeline
```bash
# Full pipeline (reads target from config.yaml)
python3 main.py run

# Specific phase only
python3 main.py run --phase 1

# Resume from a specific phase
python3 main.py run --from-phase 3

# Force re-run (skip cached phases)
python3 main.py run --force

# Use alternate config
python3 main.py run --config apple-config.yaml
```

### Manual Review
```bash
python3 main.py review
```

### Generate Report
```bash
python3 main.py report --format html --output report.html
```

### Check Status
```bash
# Show status for config's target
python3 main.py status

```

### Clear Workspace
```bash
python3 main.py clear
```

## 🔧 Configuration

`config.yaml` (all settings read from file — no CLI target override):
```yaml
target: example.com
scope: []                  # Accept all (or specify ["*.example.com"])
exclude: []
rate_limit: 50
threads: 20

# Tool paths (leave empty to use PATH)
tools: {}

# Optional API keys
chaos_api_key: ""
github_token: ""
interactsh_server: ""
```

> **Note:** The framework uses a **300-second default timeout** for tool execution. Slow tools like amass get dedicated runners with extended timeouts (180s). This is managed internally — no config needed.

## 📊 Output Structure

```
workspaces/
└── example.com/
    ├── phase1_output.json          # Discovered subdomains
    ├── phase2_output.json          # HTTP probes with tech stack
    ├── phase3_output.json          # Crawled URLs
    ├── phase4_output.json          # Discovered parameters
    ├── phase5_output.json          # Raw findings
    ├── confirmed_findings.json     # High-confidence findings
    ├── review_queue.json           # Medium-confidence (manual review)
    ├── dropped_findings.json       # Low-confidence (filtered)
    ├── exploit_results.json        # Exploitation results
    ├── raw/                        # Tool raw outputs
    ├── logs/                       # Execution logs
    └── exploits/                   # Exploitation artifacts
```

## 🧠 False Positive Filter

Intelligent scoring system:
- **Positive signals**: Response diff (+30), nuclei matcher (+25), CVE match (+20)
- **Negative signals**: WAF detected (-15), timing-only (-20), generic template (-10)
- **Routing**: ≥50=auto-confirm, 20-49=manual review, <20=drop

## 🛠️ Integrated Tools

**25+ security tools integrated:**

- **Discovery**: subfinder, amass (passive + active), assetfinder, dnsx, crt.sh, chaos API
- **Probing**: httpx, masscan, nmap, wafw00f
- **Crawling**: katana, gospider, hakrawler, waybackurls, gau, linkfinder
- **Enumeration**: ffuf, feroxbuster, paramspider, arjun, x8, gf
- **Scanning**: nuclei, secretfinder, trufflehog, nikto
- **Exploitation**: sqlmap, ghauri, dalfox, xsstrike, jwt-tool

## 📚 Documentation

- [Configuration Guide](reconx-docs/reconx_config_guide.md) - Setup and configuration
- [Tools Reference](reconx-docs/reconx_tools_reference.md) - All tools, commands, and flags
- [FP Filter Logic](reconx-docs/reconx_fp_filter_guide.md) - False positive filtering explained
- [Setup Guide](reconx-docs/setup_tools_guide.md) - Tool installation
- [Architecture](reconx-docs/ARCHITECTURE.md) - System design and data flow

## ⚠️ Disclaimer

**For authorized security testing only.** Always obtain proper authorization before testing any system you do not own.

---

<p align="">
  <b>Made with ❤️ for the security community</b><br>
  <i>Automate the boring, focus on the critical</i>
</p>
