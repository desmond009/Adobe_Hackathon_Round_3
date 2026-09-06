from audit_engine.report.validator import validate_report

_VALID = {
    "site": "example.com",
    "audited_at": "2026-09-20T14:32:00Z",
    "summary": {"total_findings": 1, "critical": 0, "high": 1, "medium": 0, "low": 0},
    "findings": [{
        "id": "F-001",
        "title": "No JSON-LD structured data on product pages",
        "severity": "high",
        "evidence": "Crawled 12 product pages; 0/12 contain schema.org markup.",
        "suggested_action": {"summary": "Add Product/Offer JSON-LD to every product page.", "priority": "high"},
    }],
}


def test_valid_report_passes():
    assert validate_report(_VALID) == []


def test_missing_required_field_fails():
    bad = {k: v for k, v in _VALID.items() if k != "summary"}
    errors = validate_report(bad)
    assert any("summary" in e for e in errors)


def test_finding_without_evidence_fails():
    bad = {**_VALID, "findings": [{k: v for k, v in _VALID["findings"][0].items() if k != "evidence"}]}
    errors = validate_report(bad)
    assert any("evidence" in e for e in errors)


def test_summary_count_mismatch_is_caught():
    bad = {**_VALID, "summary": {**_VALID["summary"], "high": 5}}
    errors = validate_report(bad)
    assert any("summary.high" in e for e in errors)


def test_duplicate_ids_are_caught():
    dup_finding = dict(_VALID["findings"][0])
    bad = {**_VALID, "findings": [_VALID["findings"][0], dup_finding],
           "summary": {**_VALID["summary"], "total_findings": 2, "high": 2}}
    errors = validate_report(bad)
    assert any("duplicate" in e for e in errors)


def test_invalid_severity_enum_fails():
    bad_finding = {**_VALID["findings"][0], "severity": "urgent"}
    bad = {**_VALID, "findings": [bad_finding]}
    errors = validate_report(bad)
    assert any("severity" in e for e in errors)
