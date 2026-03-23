"""
Pydantic models for all data schemas in the reconx framework.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VulnType(str, Enum):
    SQLI = "sqli"
    XSS = "xss"
    SSRF = "ssrf"
    XXE = "xxe"
    LFI = "lfi"
    IDOR = "idor"
    SECRET = "secret"
    CVE = "cve"
    MISCONFIGURATION = "misconfiguration"
    AUTH_BYPASS = "auth_bypass"


class Subdomain(BaseModel):
    subdomain: str
    ip: Optional[str] = None
    cname: Optional[str] = None
    asn: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    alive: bool = False


class HttpProbe(BaseModel):
    url: str
    status_code: int
    title: Optional[str] = None
    tech: List[str] = Field(default_factory=list)
    waf: Optional[str] = None
    waf_bypass_needed: bool = False
    ports: List[int] = Field(default_factory=list)
    cdn: bool = False
    ip: Optional[str] = None
    content_length: Optional[int] = None


class CrawledUrl(BaseModel):
    url: str
    source: str  # katana | waybackurls | gau | gospider | hakrawler
    method: str = "GET"  # GET | POST
    params: List[str] = Field(default_factory=list)


class Parameter(BaseModel):
    url: str
    param: str
    method: str
    pattern: Optional[str] = None  # gf tag: xss | sqli | ssrf | redirect | lfi


class SecretType(str, Enum):
    AWS_KEY = "AWS_KEY"
    GITHUB_TOKEN = "GITHUB_TOKEN"
    API_KEY = "API_KEY"
    PRIVATE_KEY = "PRIVATE_KEY"
    PASSWORD = "PASSWORD"
    OTHER = "OTHER"


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    url: str
    param: Optional[str] = None
    vuln_type: str  # sqli | xss | ssrf | xxe | lfi | idor | secret | cve | misconfiguration | auth_bypass
    tool: str
    template: Optional[str] = None
    severity: str  # critical | high | medium | low | info
    evidence: str
    request: Optional[str] = None
    response_snippet: Optional[str] = None
    confidence: str = "medium"  # high | medium | low
    confirmed: bool = False
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    score: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    def redact_evidence_for_log(self) -> str:
        """Redact sensitive content in evidence for logging."""
        if self.vuln_type == "secret" and len(self.evidence) > 10:
            return self.evidence[:6] + "***"
        return self.evidence


class PhaseOutput(BaseModel):
    phase: str
    count: int
    output_file: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExploitResult(BaseModel):
    finding_id: str
    exploit_success: bool
    poc_request: Optional[str] = None
    impact: Optional[str] = None
    evidence: Optional[str] = None
    tool_used: str
    output_path: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class Config(BaseModel):
    target: str
    scope: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)
    rate_limit: int = 50
    threads: int = 20
    timeout: int = 10
    wordlist_dirs: Optional[str] = None
    wordlist_subs: Optional[str] = None
    tools: Dict[str, str] = Field(default_factory=dict)
    nuclei_templates: Optional[str] = None
    interactsh_server: Optional[str] = None
    github_token: Optional[str] = None
    chaos_api_key: Optional[str] = None


class BaselineResponse(BaseModel):
    url: str
    status_code: int
    content_length: int
    headers: Dict[str, str] = Field(default_factory=dict)
    body_hash: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
