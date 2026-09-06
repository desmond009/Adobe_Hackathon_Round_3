"""End-to-end pipeline tests against local fixture sites.

These exercise the real crawler over real HTTP (against localhost, never the
public internet) so the crawl/parse/analyze/report pipeline is tested as a
whole, not just its unit pieces. Each fixture is designed to make specific,
falsifiable claims about which findings should and should not appear.
"""
from pathlib import Path

import pytest

from audit_engine.config import load_config
from audit_engine.orchestrator import run_audit
from audit_engine.report.validator import validate_report
from tests.integration.server import serve_fixture

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "sites"


def _finding_check_ids(report: dict) -> set[str]:
    # check_id isn't in the final report shape by name, but title is stable per check;
    # tests match on title substrings, which is what a report consumer would see too.
    return {f["title"] for f in report["findings"]}


@pytest.fixture()
def cfg():
    return load_config()


def test_good_ecommerce_site_has_few_findings_and_no_critical(cfg):
    with serve_fixture(_FIXTURES / "good_ecommerce") as base_url:
        report = run_audit(base_url, cfg)

    errors = validate_report(report)
    assert not errors, errors

    assert report["summary"]["critical"] == 0, report["findings"]
    # A well-built small site should not trip the highest-signal checks:
    titles = _finding_check_ids(report)
    assert not any("does not clearly state what the business does" in t for t in titles)
    assert not any("No Organization/WebSite structured data" in t for t in titles)
    assert not any("No XML sitemap" in t for t in titles)
    assert not any("cannot establish who the company is" in t for t in titles)


def test_spa_only_site_flags_js_dependency(cfg):
    with serve_fixture(_FIXTURES / "spa_js_only") as base_url:
        report = run_audit(base_url, cfg)

    errors = validate_report(report)
    assert not errors, errors
    titles = _finding_check_ids(report)
    assert any("materially harder to extract" in t for t in titles)


def test_poorly_structured_site_flags_multiple_categories(cfg):
    with serve_fixture(_FIXTURES / "poorly_structured") as base_url:
        report = run_audit(base_url, cfg)

    errors = validate_report(report)
    assert not errors, errors

    categories = {f["category"] for f in report["findings"]}
    # Expect signal from at least three distinct audit categories on a genuinely
    # broken site — this is the "generalization across a bad site" assertion.
    assert len(categories) >= 3, categories

    titles = _finding_check_ids(report)
    assert any("vague marketing language" in t for t in titles)
    assert any("brand" in t.lower() or "name" in t.lower() for t in titles)
    assert any("sitemap" in t.lower() for t in titles)
    assert any("canonical" in t.lower() for t in titles)

    # Every finding must carry non-empty evidence and a suggested_action (spec section 15/16).
    for f in report["findings"]:
        assert f["evidence"].strip()
        assert f["suggested_action"]["summary"].strip()
        assert f["suggested_action"]["priority"] in {"critical", "high", "medium", "low"}


def test_unreachable_site_yields_single_clear_finding_not_noise(cfg):
    """Regression test for a real bug found during development: a fully unreachable
    domain used to also emit a misleading 'no sitemap' finding on top of the real
    'site unreachable' problem. See audit_engine/analyzers/crawl_render.py."""
    report = run_audit("http://127.0.0.1:1/", cfg)  # port 1: nothing listens, connection refused
    errors = validate_report(report)
    assert not errors, errors
    assert len(report["findings"]) == 1
    assert report["findings"][0]["title"] == "Site could not be reached during the audit crawl"
    assert report["findings"][0]["severity"] == "critical"
