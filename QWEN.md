# ReconX Project State - Session Continuity Guide

> **Last Updated:** April 13, 2026
> **Branch:** `main`
> **Status:** All major features implemented and working

---

## 📋 Project Overview

**reconx** is a modular, async-based penetration testing framework with a 6-phase reconnaissance-to-exploitation pipeline.

### Key Features Implemented
- ✅ 6-Phase Pipeline (Discovery → Probing → Crawling → Enumeration → Scanning → Exploitation)
- ✅ Auto-resume from interrupted runs
- ✅ Phase dependency detection with clear error messages
- ✅ ASN/IP/CNAME extraction from dnsx
- ✅ Interactive tree reports with modern UI
- ✅ Per-phase HTML/Markdown/Tree reports
- ✅ masscan/nmap capabilities (no sudo at runtime)
- ✅ Tool source tracking per subdomain
- ✅ Interrupted run detection with log display
- ✅ Skip-installed-tools in setup_tools.sh
- ✅ Fixed `split('')` → `split('\n')` bugs in Phase 3

---

## ️ Architecture

```
Phase 1: Discovery     → subfinder, amass, assetfinder, crt.sh, chaos
    ↓ (phase1_output.json: subdomains + IPs + CNAMEs + ASNs + sources)
Phase 2: Probing       → httpx, masscan, nmap, wafw00f
    ↓ (phase2_output.json: HTTP probes + tech stack + ports)
Phase 3: Crawling      → katana, gospider, waybackurls, gau, linkfinder
    ↓ (phase3_output.json: crawled URLs + JS files)
Phase 4: Enumeration   → ffuf, feroxbuster, paramspider, arjun, gf
    ↓ (phase4_output.json: directories + parameters)
Phase 5: Scanning      → nuclei, secretfinder, trufflehog, nikto
    ↓ (phase5_output.json: findings/vulnerabilities)
FP Filter              → Scoring engine routes findings
    ↓ (confirmed_findings.json, review_queue.json, dropped_findings.json)
Phase 6: Exploitation  → sqlmap, dalfox, jwt-tool
    ↓ (exploit_results.json)
```

---

## 📁 Key File Locations

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point (Click-based) |
| `orchestrator.py` | Pipeline orchestration, auto-resume logic |
| `core/workspace.py` | Workspace management, interruption detection |
| `core/runner.py` | Async subprocess runner |
| `core/models.py` | Pydantic data models |
| `core/logger.py` | Structured JSON logging |
| `phases/phase1_discovery.py` | Subdomain discovery with IP/ASN/CNAME extraction |
| `phases/phase2_probing.py` | HTTP probing, masscan/nmap port scanning |
| `phases/phase3_crawling.py` | URL crawling (fixed split bugs) |
| `phases/phase4_enumeration.py` | Directory/parameter enumeration |
| `phases/phase5_scanning.py` | Vulnerability scanning (requires Phase 4 output) |
| `phases/phase6_exploitation.py` | Targeted exploitation |
| `reports/generator.py` | Report generation (HTML, Markdown, Tree) |
| `setup_tools.sh` | Tool installation with setcap for masscan/nmap |
| `uninstall.sh` | Cleanup with capability removal |
| `config.yaml` | Target configuration |

---

## 🔧 Recent Changes (This Session)

### Phase 1: Discovery
- **Fixed:** dnsx now extracts IPs, CNAMEs, and ASNs using `-a -resp -cname -json` flags
- **Added:** Source tracking - each subdomain tracks which tools found it
- **Added:** ASN lookup via ipinfo.io integration (fallback for dnsx)
- **Fixed:** `_check_alive()` strips protocols from httpx output to match dnsx hostnames
- **Fixed:** Netblock entries filtered from dnsx JSON output

### Phase 2: Probing
- **Fixed:** nmap runs on all IPs if masscan fails (fallback behavior)
- **Fixed:** masscan uses `sudo` prefix when not root
- **Fixed:** nmap XML output parsing with `xml.etree.ElementTree`
- **Added:** 600s timeout for nmap (dedicated runner)
- **Fixed:** Tool names simplified in spinner display (no more `wafw00f_https://...`)

### Phase 3: Crawling
- **Fixed:** `split('')` → `split('\n')` in waybackurls, gau, hakrawler, linkfinder
- **Impact:** Phase 3 now produces results (was returning 0 items before)

### Phase 4: Enumeration
- **Fixed:** Checks file existence before checking content (empty file ≠ missing file)
- **Fixed:** Saves empty output on early return so phase is marked complete

### Phase 5: Scanning
- **Fixed:** Checks `phase4_output.json` exists before failing
- **Fixed:** Now requires Phase 4 output (was missing dependency check)

### Phase 6: Exploitation
- **Fixed:** Checks `confirmed_findings.json` exists before failing

### Orchestrator
- **Added:** Auto-resume from next runnable phase
- **Added:** Interrupted run detection (analyzes orchestrator.log)
- **Added:** Clear error messages when trying to run phase without dependencies
- **Added:** `--force` bypasses all dependency checks

### Reports
- **Added:** Per-phase HTML reports with searchable tables
- **Added:** Per-phase Markdown reports rendered in terminal
- **Added:** Interactive tree report with:
  - Modern CSS variables theming
  - Gradient header text
  - Rounded cards with hover animations
  - Expand/collapse nodes
  - Color-coded ASN badges
  - Source tags per subdomain
  - Keyboard accessibility
  - Responsive design
- **Added:** Auto-generate reports after each phase completes

### Setup Tools
- **Added:** `setcap cap_net_raw+ep` for masscan (no sudo at runtime)
- **Added:** `setcap cap_net_raw,cap_net_admin+eip` for nmap
- **Added:** Skip already-installed tools check
- **Fixed:** Banner ANSI code rendering (echo → printf)
- **Fixed:** SecLists update (git reset --hard before pull)

### Uninstall
- **Added:** `setcap -r` removal for masscan/nmap before deletion

---

## 🚀 Commands Reference

### Running the Pipeline
```bash
# Full pipeline
python3 main.py run

# Auto-resumes from last completed phase
python3 main.py run

# Specific phase
python3 main.py run --phase 1

# Resume from phase
python3 main.py run --from-phase 3

# Force re-run
python3 main.py run --force

# Alternate config
python3 main.py run --config apple-config.yaml
```

### Reports
```bash
# Per-phase HTML (opens in browser)
python3 main.py report --phase 1 --format html

# Per-phase Markdown (renders in terminal)
python3 main.py report --phase 1 --format markdown

# Interactive tree report
python3 main.py report --phase 1 --format tree

# Full pipeline report
python3 main.py report --format html
```

### Status & Management
```bash
python3 main.py status      # Show workspace status
python3 main.py review      # Open manual review TUI
python3 main.py clear       # Clear workspace
python3 main.py init        # Create config template
```

### Setup
```bash
sudo bash setup_tools.sh    # Install all tools
```

---

## 🐛 Known Issues & Workarounds

| Issue | Status | Workaround |
|-------|--------|------------|
| masscan needs sudo | Fixed (setcap) | Run `sudo bash setup_tools.sh` to apply capabilities |
| nmap `-oJ` invalid format | Fixed | Now uses `-oX` XML with custom parser |
| Phase 3 returns 0 items | Fixed | `split('')` → `split('\n')` |
| Phase 5 requires Phase 4 | Fixed | Added dependency check |
| Tree report not rendering | Fixed | `DOMContentLoaded` event timing fixed |

---

## 📊 Data Flow

### Phase 1 Output (`phase1_output.json`)
```json
[
  {
    "subdomain": "app.spendesk.com",
    "ip": "104.21.67.58",
    "cname": "app.spendesk.com.cdn.cloudflare.net",
    "asn": "AS13335 Cloudflare, Inc.",
    "sources": ["subfinder", "amass", "chaos"],
    "alive": true
  }
]
```

### Phase 2 Output (`phase2_output.json`)
```json
[
  {
    "url": "https://app.spendesk.com",
    "status_code": 200,
    "title": "Spendesk",
    "tech": ["Cloudflare", "HSTS"],
    "waf": null,
    "waf_bypass_needed": false,
    "ports": [80, 443],
    "cdn": true,
    "ip": "104.21.67.58",
    "content_length": 12345
  }
]
```

---

## 🔐 Security Notes

- API keys stored in `config.yaml` (chaos_api_key, github_token)
- Secret redaction in logs (first 6 chars + `***`)
- Scope enforcement via `scope` and `exclude` config
- Rate limiting via async semaphore
- masscan/nmap use capabilities instead of sudo

---

## 📝 Next Steps (Future Enhancements)

- [ ] Add subdomain categorization (marketing, infrastructure, etc.) to tree report
- [ ] Add clickable nodes in tree report to filter table
- [ ] Add PDF report export
- [ ] Add Slack/Discord webhook notifications
- [ ] Add WebSocket live progress updates
- [ ] Add subdomain takeover detection
- [ ] Add certificate transparency monitoring
- [ ] Add GitHub repo enumeration

---

## 🧪 Testing Checklist

Before each release:
- [ ] Phase 1 completes with IPs, CNAMEs, ASNs populated
- [ ] Phase 2 runs masscan/nmap successfully
- [ ] Phase 3 produces URL results (>0 items)
- [ ] Phase 4 runs with Phase 3 output
- [ ] Phase 5 runs with Phase 4 output
- [ ] Tree report renders correctly in browser
- [ ] Markdown report renders in terminal
- [ ] Auto-resume works after interruption
- [ ] `--force` bypasses all checks
- [ ] `setup_tools.sh` applies capabilities correctly

---

## 💡 Tips for Next Session

1. **If tree report shows blank:** Check browser console for JS errors
2. **If Phase 3 returns 0:** Verify `split('\n')` fix is in place
3. **If masscan fails:** Run `sudo bash setup_tools.sh` to reapply capabilities
4. **To test auto-resume:** Run Phase 1, then `python3 main.py run` (should skip Phase 1)
5. **To regenerate reports:** `python3 main.py report --phase 1 --format tree`

---

*This file should be updated at the end of each development session to maintain continuity.*
