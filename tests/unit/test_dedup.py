from audit_engine.intelligence.dedup import deduplicate
from audit_engine.models import Evidence, Finding, Recommendation


def _finding(id_, check_id, category, urls) -> Finding:
    return Finding(
        id=id_, check_id=check_id, category=category, title=check_id, severity="high", confidence=0.8,
        evidence=[Evidence(source_url=urls[0], signal="s", observed_value="v")],
        suggested_action=Recommendation(summary="fix it", priority="high"),
        affected_urls=urls,
    )


def test_exact_duplicate_candidates_are_merged():
    f1 = _finding("F-001", "no_sitemap", "crawlability", ["https://example.com/"])
    f2 = _finding("F-002", "no_sitemap", "crawlability", ["https://example.com/"])
    result = deduplicate([f1, f2])
    assert len(result) == 1


def test_related_but_distinct_findings_are_grouped_not_merged():
    """The spec's own example: content-extractability + structured-data + engagement
    findings about the same product page are related but must remain separate,
    actionable findings — only tagged as related."""
    product_url = "https://example.com/products/widget"
    f1 = _finding("F-001", "missing_product_schema", "structured_data", [product_url])
    f2 = _finding("F-002", "unanswerable_what", "content_extractability", [product_url])
    f3 = _finding("F-003", "thin_internal_linking", "engagement", [product_url])
    result = deduplicate([f1, f2, f3])
    assert len(result) == 3  # nothing collapsed
    assert len({f.related_group for f in result}) == 1  # but all tagged as one related group
    assert all(f.related_group is not None for f in result)


def test_unrelated_findings_get_no_group():
    f1 = _finding("F-001", "no_sitemap", "crawlability", ["https://example.com/"])
    f2 = _finding("F-002", "missing_about_identity", "entity_identity", ["https://example.com/other"])
    result = deduplicate([f1, f2])
    assert all(f.related_group is None for f in result)


def test_same_category_overlap_is_not_grouped():
    """Grouping is a cross-category signal only; two findings in the same category
    that happen to share a URL are just two findings in that category, not a 'related
    group' — the category-level distinction already separates them."""
    f1 = _finding("F-001", "no_sitemap", "crawlability", ["https://example.com/"])
    f2 = _finding("F-002", "missing_canonical", "crawlability", ["https://example.com/"])
    result = deduplicate([f1, f2])
    assert all(f.related_group is None for f in result)
