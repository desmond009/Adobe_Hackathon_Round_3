"""Assembles the final AuditResult from a prioritized finding list."""
from __future__ import annotations

from datetime import datetime, timezone

from audit_engine.models import AuditResult, AuditSummary, CrawlStats, Finding


def build_audit_result(
    site: str, findings: list[Finding], crawl_stats: CrawlStats, limitations: list[str], max_findings: int,
) -> AuditResult:
    findings = findings[:max_findings]
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1

    summary = AuditSummary(
        total_findings=len(findings),
        critical=counts["critical"],
        high=counts["high"],
        medium=counts["medium"],
        low=counts["low"],
    )

    return AuditResult(
        site=site,
        audited_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        summary=summary,
        findings=findings,
        limitations=limitations,
        crawl_stats=crawl_stats,
    )
