"""Deterministic severity scoring and finding construction.

Severity is a weighted sum, not a raw product, of four 0..1 inputs:

    composite = 0.35*impact + 0.25*scope + 0.20*confidence + 0.20*business_importance

`impact` and `business_importance` come from the static check catalog.
`scope` and `confidence` are supplied by the analyzer at the point it found
the issue (e.g. scope = affected_pages / sampled_pages).

A weighted sum (rather than a product of four <=1 numbers) is used deliberately:
a product collapses toward zero as soon as any one factor is moderate, which
would silently suppress real, narrow-but-severe issues (e.g. a critical
mismatch found with high confidence on a single, highly important page). The
weighted sum keeps each dimension's contribution legible and auditable.

Thresholds map the composite to a Severity band. Findings below the
confidence floor (config: analysis.confidence_threshold) are never
constructed — this is the primary false-positive control point.
"""
from __future__ import annotations

from dataclasses import dataclass

from audit_engine.models import Evidence, Finding, Recommendation, Severity

_WEIGHTS = {"impact": 0.35, "scope": 0.25, "confidence": 0.20, "business_importance": 0.20}

_THRESHOLDS = (
    (0.75, Severity.CRITICAL),
    (0.55, Severity.HIGH),
    (0.35, Severity.MEDIUM),
)


def compute_composite_score(impact: float, scope: float, confidence: float, business_importance: float) -> float:
    return (
        _WEIGHTS["impact"] * _clamp(impact)
        + _WEIGHTS["scope"] * _clamp(scope)
        + _WEIGHTS["confidence"] * _clamp(confidence)
        + _WEIGHTS["business_importance"] * _clamp(business_importance)
    )


def score_to_severity(score: float) -> Severity:
    for floor, severity in _THRESHOLDS:
        if score >= floor:
            return severity
    return Severity.LOW


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class FindingCandidate:
    """What an analyzer builds; the factory turns this into a Finding or rejects it."""

    check_id: str
    evidence: list[Evidence]
    scope: float                     # fraction of sampled/relevant pages exhibiting the issue (0..1)
    confidence: float                # analyzer's confidence that the signal is real and relevant (0..1)
    recommendation_summary: str
    recommendation_rationale: str = ""
    affected_urls: list[str] | None = None
    title_override: str | None = None
    proactive: bool = False


def build_finding(candidate: FindingCandidate, finding_id: str, confidence_threshold: float) -> Finding | None:
    """Apply the false-positive gate, then construct a Finding, or return None."""
    from audit_engine.catalog import get as get_check  # local import avoids a cycle at module load

    check = get_check(candidate.check_id)

    if not candidate.evidence:
        return None  # never emit a finding without evidence (spec section 15/16)
    if candidate.confidence < confidence_threshold:
        return None  # false-positive control: drop low-confidence candidates outright

    score = compute_composite_score(
        impact=check.impact,
        scope=candidate.scope,
        confidence=candidate.confidence,
        business_importance=check.business_importance,
    )
    severity = score_to_severity(score)
    priority = severity.value

    return Finding(
        id=finding_id,
        check_id=check.id,
        category=check.category,
        title=candidate.title_override or check.title,
        severity=severity.value,
        confidence=round(candidate.confidence, 3),
        evidence=candidate.evidence,
        suggested_action=Recommendation(
            summary=candidate.recommendation_summary,
            priority=priority,
            rationale=candidate.recommendation_rationale or None,
            proactive=candidate.proactive or check.proactive,
        ),
        root_cause_key=f"{check.category}:{check.id}",
        affected_urls=candidate.affected_urls or sorted({e.source_url for e in candidate.evidence}),
    )
