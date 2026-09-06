"""Typed internal data contracts.

Every component in the pipeline communicates through these types instead of
ad-hoc dictionaries. This makes it structurally difficult for an analyzer to
emit a malformed Finding, and gives every stage (crawler -> parsers ->
analyzers -> intelligence -> report) a stable, documented interface.

Pipeline shape:

    AuditRequest -> SiteSnapshot (pages: list[PageSnapshot])
                 -> [Evidence, ...] (per analyzer)
                 -> [Finding, ...]  (evidence + severity + suggested_action)
                 -> AuditResult     (summary + findings, final schema)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(str, Enum):
    CRAWLABILITY = "crawlability"
    STRUCTURED_DATA = "structured_data"
    CONTENT_EXTRACTABILITY = "content_extractability"
    FRESHNESS_CORROBORATION = "freshness_corroboration"
    ENTITY_IDENTITY = "entity_identity"
    ENGAGEMENT = "engagement"


# --------------------------------------------------------------------------- #
# Request
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class AuditRequest:
    """Validated, normalized input to the orchestrator."""

    raw_input: str
    url: str            # normalized seed URL, e.g. https://example.com/
    domain: str          # registrable-ish host, e.g. example.com
    requested_at: str    # ISO-8601 UTC timestamp


# --------------------------------------------------------------------------- #
# Site snapshot (the shared, immutable crawl artifact every analyzer consumes)
# --------------------------------------------------------------------------- #

@dataclass
class RenderDelta:
    """Result of comparing raw HTML to a rendered DOM for one page, when available."""

    method: str                    # "playwright" | "heuristic_only"
    rendered: bool                 # True if an actual browser render happened
    raw_word_count: int
    rendered_word_count: Optional[int] = None
    raw_structured_data_count: int = 0
    rendered_structured_data_count: Optional[int] = None
    js_dependency_score: float = 0.0   # 0..1 heuristic score, higher = more JS-dependent
    notes: str = ""


@dataclass
class PageSnapshot:
    """Everything the pipeline knows about one crawled page."""

    url: str
    final_url: str
    depth: int
    status: Optional[int]
    ok: bool
    error: Optional[str]
    content_type: Optional[str]
    headers: dict[str, str] = field(default_factory=dict)
    fetched_at: str = ""
    raw_html: str = ""
    text: str = ""
    word_count: int = 0
    title: Optional[str] = None
    meta: dict[str, str] = field(default_factory=dict)
    headings: list[tuple[int, str]] = field(default_factory=list)
    links_internal: list[str] = field(default_factory=list)
    links_external: list[str] = field(default_factory=list)
    canonical: Optional[str] = None
    lang: Optional[str] = None
    structured_data: list[dict] = field(default_factory=list)  # normalized blocks, see parsing/structured_data.py
    contact_signals: dict[str, list[str]] = field(default_factory=dict)  # emails/phones/addresses found
    render_delta: Optional[RenderDelta] = None
    is_priority_page: bool = False
    page_role: Optional[str] = None  # "home" | "product" | "about" | "contact" | "pricing" | "other"


@dataclass
class CrawlStats:
    urls_discovered: int = 0
    pages_fetched: int = 0
    pages_failed: int = 0
    pages_skipped_robots: int = 0
    duration_s: float = 0.0
    stopped_reason: str = "completed"  # "completed" | "max_pages" | "time_budget" | "no_more_urls"


@dataclass
class SiteSnapshot:
    """Immutable, shared crawl artifact consumed by every specialized skill."""

    domain: str
    root_url: str
    robots_txt_found: bool
    robots_allowed_root: bool
    robots_disallow_rules: list[str]
    sitemap_urls: list[str]
    pages: list[PageSnapshot]
    crawl_started_at: str
    crawl_finished_at: str
    crawl_stats: CrawlStats

    def page_by_url(self, url: str) -> Optional[PageSnapshot]:
        for p in self.pages:
            if p.url == url or p.final_url == url:
                return p
        return None

    def ok_pages(self) -> list[PageSnapshot]:
        return [p for p in self.pages if p.ok]


# --------------------------------------------------------------------------- #
# Evidence / Finding / Recommendation
# --------------------------------------------------------------------------- #

@dataclass
class Evidence:
    """One concrete, attributable observation backing a finding."""

    source_url: str
    signal: str                 # short machine-readable signal name, e.g. "jsonld_product_missing"
    observed_value: str         # what was actually observed
    expected_value: Optional[str] = None
    confidence: float = 1.0     # 0..1, confidence in this individual observation


@dataclass
class Recommendation:
    summary: str
    priority: str                 # one of Severity values
    rationale: Optional[str] = None
    proactive: bool = False       # True if this is a proactive suggestion, not tied to a defect


@dataclass
class Finding:
    """A single, evidence-backed, actionable audit finding."""

    id: str
    check_id: str
    category: str
    title: str
    severity: str
    confidence: float
    evidence: list[Evidence]
    suggested_action: Recommendation
    root_cause_key: str = ""     # used by the deduplication layer to group related findings
    affected_urls: list[str] = field(default_factory=list)
    related_group: Optional[str] = None   # set by intelligence/dedup.py when findings share a root cause
    priority_rank: Optional[int] = None   # set by intelligence/prioritize.py


@dataclass
class AuditSummary:
    total_findings: int
    critical: int
    high: int
    medium: int
    low: int = 0


@dataclass
class AuditResult:
    """Top-level result. `to_report_dict()` renders the mandated final JSON shape."""

    site: str
    audited_at: str
    summary: AuditSummary
    findings: list[Finding]
    limitations: list[str] = field(default_factory=list)
    crawl_stats: Optional[CrawlStats] = None

    def to_report_dict(self) -> dict[str, Any]:
        """Render the schema mandated by the challenge spec.

        Required fields per finding: id, title, severity, evidence, suggested_action.
        `evidence` there is the single human-readable string the spec's example shows.
        We additionally attach `category`, `confidence`, `evidence_detail` (the full
        structured evidence list) and `affected_urls` as non-breaking enrichment —
        extra fields, not a violation of the required shape (see report/schema.json,
        additionalProperties is intentionally permissive at every level).
        """
        findings_out = []
        for f in self.findings:
            evidence_text = "; ".join(
                f"{e.observed_value}" + (f" (expected: {e.expected_value})" if e.expected_value else "")
                for e in f.evidence
            )
            findings_out.append({
                "id": f.id,
                "category": f.category,
                "title": f.title,
                "severity": f.severity,
                "confidence": round(f.confidence, 2),
                "evidence": evidence_text,
                "evidence_detail": [
                    {
                        "url": e.source_url,
                        "signal": e.signal,
                        "observation": e.observed_value,
                        "expected": e.expected_value,
                        "confidence": round(e.confidence, 2),
                    }
                    for e in f.evidence
                ],
                "affected_urls": f.affected_urls,
                "related_group": f.related_group,
                "priority_rank": f.priority_rank,
                "suggested_action": {
                    "summary": f.suggested_action.summary,
                    "priority": f.suggested_action.priority,
                    "rationale": f.suggested_action.rationale,
                    "proactive": f.suggested_action.proactive,
                },
            })
        return {
            "site": self.site,
            "audited_at": self.audited_at,
            "summary": {
                "total_findings": self.summary.total_findings,
                "critical": self.summary.critical,
                "high": self.summary.high,
                "medium": self.summary.medium,
                "low": self.summary.low,
            },
            "findings": findings_out,
            "limitations": self.limitations,
        }
