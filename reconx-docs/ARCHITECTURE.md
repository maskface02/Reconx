# reconx Architecture Documentation

## Overview

reconx is a modular, async-based penetration testing framework with a 6-phase pipeline architecture.

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RECONX PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   Phase 1    │───▶│   Phase 2    │───▶│   Phase 3    │                  │
│  │  Discovery   │    │   Probing    │    │   Crawling   │                  │
│  │              │    │              │    │              │                  │
│  │ subfinder    │    │ httpx        │    │ katana       │                  │
│  │ amass        │    │ masscan      │    │ gospider     │                  │
│  │ assetfinder  │    │ nmap         │    │ waybackurls  │                  │
│  │ crt.sh       │    │ wafw00f      │    │ gau          │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│         │                   │                   │                          │
│         ▼                   ▼                   ▼                          │
│  phase1_output.json   phase2_output.json   phase3_output.json              │
│  list[Subdomain]      list[HttpProbe]      list[CrawledUrl]                │
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   Phase 4    │───▶│   Phase 5    │───▶│  FP Filter   │                  │
│  │ Enumeration  │    │   Scanning   │    │              │                  │
│  │              │    │              │    │              │                  │
│  │ ffuf         │    │ nuclei       │    │ Scoring      │                  │
│  │ feroxbuster  │    │ nikto        │    │ Engine       │                  │
│  │ paramspider  │    │ secretfinder │    │              │                  │
│  │ arjun        │    │ trufflehog   │    │ Confidence   │                  │
│  │ gf           │    │              │    │ Routing      │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│         │                   │                   │                          │
│         ▼                   ▼                   ▼                          │
│  phase4_output.json   phase5_output.json   confirmed_findings.json         │
│  list[Parameter]      list[Finding]        review_queue.json               │
│                                            dropped_findings.json           │
│                                                                             │
│  ┌──────────────┐                                                          │
│  │   Phase 6    │                                                          │
│  │ Exploitation │                                                          │
│  │              │                                                          │
│  │ sqlmap       │                                                          │
│  │ dalfox       │                                                          │
│  │ ssrfire      │                                                          │
│  │ jwt-tool     │                                                          │
│  └──────────────┘                                                          │
│         │                                                                  │
│         ▼                                                                  │
│  exploit_results.json                                                      │
│  list[ExploitResult]                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Workspace Manager
- Creates per-target directory structure
- Handles file I/O for phase outputs
- Manages cache/state for resume support

### 2. Async Runner
- Semaphore-based rate limiting
- Timeout handling
- Parallel execution support
- Graceful error handling

### 3. Logger
- Structured JSON logging to files
- Rich console output
- Phase context tracking
- Secret redaction

### 4. False Positive Filter
- Weighted scoring system
- Baseline response comparison
- Confidence-based routing
- Cross-tool validation

## Class Hierarchy

```
BasePhase (ABC)
├── Phase1Discovery
├── Phase2Probing
├── Phase3Crawling
├── Phase4Enumeration
├── Phase5Scanning
└── Phase6Exploitation

FPFilter (standalone)

Workspace (file manager)
AsyncRunner (subprocess manager)
StructuredLogger (logging)
ReviewQueueTUI (user interface)
ReportGenerator (output)
```

## Data Models

### Subdomain
```python
{
  "subdomain": "api.example.com",
  "ip": "192.168.1.1",
  "cname": "api.example.com.herokudns.com",
  "asn": "AS12345",
  "sources": ["subfinder", "amass"],
  "alive": true
}
```

### HttpProbe
```python
{
  "url": "https://api.example.com",
  "status_code": 200,
  "title": "API Documentation",
  "tech": ["nginx", "Express"],
  "waf": "Cloudflare",
  "waf_bypass_needed": true,
  "ports": [80, 443, 8080],
  "cdn": true,
  "ip": "192.168.1.1",
  "content_length": 1234
}
```

### Finding
```python
{
  "id": "a1b2c3d4",
  "url": "https://api.example.com/users?id=1",
  "param": "id",
  "vuln_type": "sqli",
  "tool": "nuclei",
  "template": "CVE-2023-1234",
  "severity": "high",
  "evidence": "SQL syntax error near '1''",
  "request": "GET /users?id=1' HTTP/1.1...",
  "response_snippet": "...SQL syntax error...",
  "confidence": "high",
  "confirmed": true,
  "score": 75,
  "score_breakdown": {
    "response_diff_confirmed": true,
    "nuclei_matcher_positive": true,
    "cve_version_match": true
  }
}
```

## Scoring Algorithm

```python
score = 0

# Positive signals
if response_differs_from_baseline:  score += 30
if nuclei_matcher_positive:         score += 25
if multiple_tools_agree:            score += 20
if cve_version_match:               score += 20

# Negative signals
if waf_detected:                    score -= 15
if generic_template:                score -= 10
if timing_based_only:               score -= 20
if single_tool_no_evidence:         score -= 15

# Routing
if score >= 50:   confidence = "high"    → confirmed_findings.json
if 20 <= score < 50: confidence = "medium" → review_queue.json
if score < 20:    confidence = "low"     → dropped_findings.json
```

## Async Execution Model

```python
# Each phase runs tools concurrently
async def run(self):
    tasks = []

    # Add all tool tasks
    if tool_available('subfinder'):
        tasks.append(self._run_subfinder())
    if tool_available('amass'):
        tasks.append(self._run_amass())

    # Run all in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Task failed: {result}")
        else:
            process_result(result)
```

## Timeout Architecture

The framework uses a **layered timeout strategy**:

| Layer | Timeout | Notes |
|-------|---------|-------|
| **Default runner** | 300s | Used by all phases for most tools |
| **Phase 1 dedicated runners** | 300s | Subfinder, amass passive, amass active |
| **HTTP fetch (curl)** | 30s | Used for crt.sh and Chaos API |

**Key design decisions:**
- Slow tools use **dedicated AsyncRunner instances** with custom timeouts
- Amass writes incrementally to files — results are captured even on timeout
- Tool failures are logged with descriptive error messages
- Phase 1 continues with partial results if individual tools fail

## Error Handling Strategy

1. **Tool Not Found**: Log warning, skip tool, continue
2. **Tool Timeout**: Kill process, log error, continue
3. **Zero Output**: Log warning, save empty output file, continue to next phase
4. **Missing Phase Dependencies**: Raise `PhaseException` with actionable message showing exact command to run
5. **Malformed JSON**: Attempt repair, re-run if needed
6. **Phase Exception**: Stop pipeline, show red error panel with guidance

## Auto-Resume System

The framework automatically detects which phase to start from:

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → FP Filter → Phase 6
  ↓         ↓         ↓         ↓         ↓          ↓          ↓
config   phase1    phase2    phase3    phase4   phase5+   confirmed_
         .json     .json     .json     .json    .json    findings.json
                   +urls.txt           +all_urls +js_files
                                       .txt      .txt
```

**Behavior:**
- `python3 main.py run` → Auto-detects next runnable phase, skips completed ones
- `python3 main.py run --phase 4` → Fails with clear error if Phase 3 output missing
- `python3 main.py run --force` → Re-runs requested phase regardless of cache

## Interrupted Run Detection

The system analyzes `orchestrator.log` to detect if a previous run was interrupted:
- Finds phase_start events without matching phase_end
- Shows target, stopped phase, and last 5 log entries
- Automatically resumes from the next runnable phase

## Tool Capabilities (No Sudo at Runtime)

masscan and nmap use Linux capabilities (`cap_net_raw`) instead of requiring sudo:
- `setcap cap_net_raw+ep ~/.local/bin/masscan`
- Applied automatically by `setup_tools.sh`
- Both tools run like any other tool — no privilege escalation needed

## Security Considerations

1. **Secret Redaction**: API keys redacted in logs (first 6 chars + ***)
2. **Scope Enforcement**: All URLs checked against scope/exclude lists
3. **Rate Limiting**: Global semaphore across all async operations
4. **Read-Only Operations**: Secret validation uses read-only API calls
5. **No Hardcoded Paths**: All tool paths from config
