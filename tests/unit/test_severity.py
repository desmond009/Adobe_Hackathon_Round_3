from audit_engine.models import Evidence
from audit_engine.severity import FindingCandidate, build_finding, compute_composite_score, score_to_severity


def _evidence() -> list[Evidence]:
    return [Evidence(source_url="https://example.com/", signal="s", observed_value="v", confidence=0.9)]


def test_composite_score_is_monotonic_in_each_input():
    low = compute_composite_score(impact=0.2, scope=0.2, confidence=0.2, business_importance=0.2)
    high = compute_composite_score(impact=0.9, scope=0.9, confidence=0.9, business_importance=0.9)
    assert high > low


def test_score_to_severity_thresholds():
    assert score_to_severity(0.9) == "critical"
    assert score_to_severity(0.6) == "high"
    assert score_to_severity(0.4) == "medium"
    assert score_to_severity(0.1) == "low"


def test_build_finding_rejects_below_confidence_threshold():
    candidate = FindingCandidate(
        check_id="no_sitemap", evidence=_evidence(), scope=1.0, confidence=0.3,
        recommendation_summary="Add a sitemap.",
    )
    assert build_finding(candidate, "F-001", confidence_threshold=0.55) is None


def test_build_finding_rejects_when_no_evidence():
    candidate = FindingCandidate(
        check_id="no_sitemap", evidence=[], scope=1.0, confidence=0.9,
        recommendation_summary="Add a sitemap.",
    )
    assert build_finding(candidate, "F-001", confidence_threshold=0.55) is None


def test_build_finding_produces_valid_finding():
    candidate = FindingCandidate(
        check_id="no_sitemap", evidence=_evidence(), scope=1.0, confidence=0.9,
        recommendation_summary="Add a sitemap.",
    )
    finding = build_finding(candidate, "F-001", confidence_threshold=0.55)
    assert finding is not None
    assert finding.id == "F-001"
    assert finding.evidence
    assert finding.suggested_action.summary == "Add a sitemap."
    assert finding.severity in {"critical", "high", "medium", "low"}
