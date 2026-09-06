"""The audit orchestrator: validate -> crawl -> analyze -> synthesize -> report.

Deliberately thin (spec section 23): this module contains no domain-specific
audit logic of its own. It validates input, builds the shared SiteSnapshot
once, fans out to the six specialized analyzers, and hands their candidates
to the shared severity/dedup/recommend/prioritize/report pipeline. Every
piece of actual detection logic lives in audit_engine/analyzers/*.
"""
from __future__ import annotations

import itertools
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from audit_engine.analyzers import (
    content_extractability, crawl_render, engagement,
    entity_identity, freshness_corroboration, structured_data_audit,
)
from audit_engine.config import Config, load_config
from audit_engine.crawler.crawl import crawl_site
from audit_engine.crawler.url_utils import ensure_scheme, normalize_url, registrable_domain
from audit_engine.intelligence.dedup import deduplicate
from audit_engine.intelligence.prioritize import prioritize
from audit_engine.intelligence.recommend import refine_recommendations
from audit_engine.logging_utils import log
from audit_engine.models import AuditRequest, Finding
from audit_engine.report.builder import build_audit_result
from audit_engine.report.validator import validate_report
from audit_engine.severity import build_finding

_ANALYZERS = [
    ("crawl-render-audit", crawl_render),
    ("structured-data-audit", structured_data_audit),
    ("content-extractability-audit", content_extractability),
    ("freshness-corroboration-audit", freshness_corroboration),
    ("entity-identity-audit", entity_identity),
    ("engagement-audit", engagement),
]

class InvalidAuditRequestError(ValueError):
    pass


def build_audit_request(raw_input: str) -> AuditRequest:
    """Validate and normalize user input into a seed URL + domain."""
    candidate = raw_input.strip()
    if not candidate:
        raise InvalidAuditRequestError("Empty site/URL provided.")
    candidate = ensure_scheme(candidate)

    parsed = urlparse(candidate)
    if not parsed.netloc or "." not in parsed.netloc:
        raise InvalidAuditRequestError(f"'{raw_input}' does not look like a valid domain or URL.")

    normalized = normalize_url(candidate)
    domain = registrable_domain(parsed.netloc.split(":")[0])
    return AuditRequest(
        raw_input=raw_input,
        url=normalized,
        domain=domain,
        requested_at=datetime.now(timezone.utc).isoformat(),
    )


def run_audit(raw_input: str, config: Config | None = None) -> dict:
    cfg = config or load_config()
    request = build_audit_request(raw_input)
    limitations: list[str] = []

    log("AUDIT", f"Starting audit for {request.domain}")

    snapshot = crawl_site(request.url, cfg)
    log("CRAWLER", f"robots.txt {'found' if snapshot.robots_txt_found else 'not found'}; "
                    f"allowed={snapshot.robots_allowed_root}")
    log("CRAWLER", f"{snapshot.crawl_stats.urls_discovered} URLs discovered, "
                    f"{snapshot.crawl_stats.pages_fetched} pages crawled "
                    f"({snapshot.crawl_stats.pages_failed} failed, stopped: {snapshot.crawl_stats.stopped_reason})")

    if not snapshot.ok_pages():
        limitations.append(
            f"No pages could be successfully crawled for {request.domain}; the report below reflects "
            "crawl-level findings only (robots/DNS/connectivity), not content analysis."
        )

    id_counter = itertools.count(1)
    all_findings: list[Finding] = []
    confidence_threshold = cfg.get("analysis", "confidence_threshold", 0.55)

    for skill_name, module in _ANALYZERS:
        try:
            candidates = module.analyze(snapshot, cfg)
        except Exception as exc:  # noqa: BLE001 - one analyzer failing must not sink the whole audit
            log(skill_name.upper(), f"analyzer raised {exc!r}; skipping this category for this run")
            limitations.append(f"{skill_name} could not complete: {exc}")
            continue

        produced = 0
        for candidate in candidates:
            finding_id = f"F-{next(id_counter):03d}"
            finding = build_finding(candidate, finding_id, confidence_threshold)
            if finding is not None:
                all_findings.append(finding)
                produced += 1
        log(skill_name.upper(), f"{len(candidates)} candidate(s) evaluated, {produced} finding(s) emitted")

    log("ORCHESTRATOR", f"{len(all_findings)} raw findings before deduplication")
    all_findings = deduplicate(all_findings)
    log("ORCHESTRATOR", f"{len(all_findings)} findings after deduplication")

    all_findings = refine_recommendations(all_findings, cfg)
    all_findings = prioritize(all_findings)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        limitations.append(
            "LLM interpretation layer ran in deterministic-fallback mode (no ANTHROPIC_API_KEY set); "
            "all findings and recommendations below are rule-based, not LLM-generated."
        )
    limitations.append(
        "External corroboration was not performed: this build only observes and cross-checks on-site "
        "facts. No claim in this report should be read as independently verified against outside sources."
    )
    if not snapshot.sitemap_urls and snapshot.crawl_stats.pages_fetched < 5:
        limitations.append(
            "Crawl coverage was small (no sitemap, few reachable pages); scope percentages in evidence "
            "reflect the sampled pages only, not necessarily the whole site."
        )

    max_findings = cfg.get("report", "max_findings", 30)
    result = build_audit_result(request.domain, all_findings, snapshot.crawl_stats, limitations, max_findings)
    report = result.to_report_dict()

    errors = validate_report(report)
    if errors:
        log("REPORT", f"validation FAILED: {errors}")
        raise RuntimeError(f"Final report failed schema validation: {errors}")

    log("REPORT", f"Final report generated with {len(report['findings'])} findings")
    return report
