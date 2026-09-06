"""Deterministic recommendation prioritization.

priority_score = impact x scope-adjusted-confidence x implementation_leverage

This is a relative ranking signal only (used to order findings and assign
priority_rank), separate from severity.py's weighted-sum banding used for the
severity label itself. Using the spec's literal multiplicative formula here
is appropriate because ranking only needs relative order, not stable
thresholds — unlike severity, nothing downstream branches on an absolute
priority_score value.
"""
from __future__ import annotations

from audit_engine.catalog import get as get_check, implementation_leverage
from audit_engine.models import Finding


def priority_score(finding: Finding) -> float:
    check = get_check(finding.check_id)
    leverage = implementation_leverage(finding.category)
    # scope isn't stored on Finding directly; confidence already folds in the
    # analyzer's scope-awareness (see severity.build_finding), so we reuse it here
    # alongside the catalog's static impact to avoid re-deriving scope from evidence.
    return check.impact * finding.confidence * leverage


def prioritize(findings: list[Finding]) -> list[Finding]:
    """Sort by (severity rank desc, priority_score desc) and assign priority_rank."""
    severity_rank = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    ordered = sorted(
        findings,
        key=lambda f: (severity_rank.get(f.severity, 0), priority_score(f)),
        reverse=True,
    )
    for i, f in enumerate(ordered, start=1):
        f.priority_rank = i
    return ordered
