"""Recommendation refinement pass.

Runs after severity scoring and deduplication, before final prioritization.
Every finding already carries a complete, deterministic, schema-valid
suggested_action from its analyzer (see FindingCandidate.recommendation_summary) —
this pass only optionally sharpens the top N by severity via the LLM layer.
Findings beyond that cap keep their deterministic recommendation untouched,
which is never a degraded output, just a plainer one.
"""
from __future__ import annotations

from audit_engine.intelligence.llm_interpret import refine_recommendation
from audit_engine.models import Finding

_MAX_LLM_REFINEMENTS = 8


def refine_recommendations(findings: list[Finding], cfg) -> list[Finding]:
    severity_rank = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    by_severity = sorted(findings, key=lambda f: severity_rank.get(f.severity, 0), reverse=True)

    for finding in by_severity[:_MAX_LLM_REFINEMENTS]:
        evidence_texts = [e.observed_value for e in finding.evidence]
        summary, rationale, used_llm = refine_recommendation(
            title=finding.title,
            category=finding.category,
            evidence_texts=evidence_texts,
            deterministic_summary=finding.suggested_action.summary,
            deterministic_rationale=finding.suggested_action.rationale or "",
            cfg=cfg,
        )
        finding.suggested_action.summary = summary
        finding.suggested_action.rationale = rationale or finding.suggested_action.rationale
    return findings
