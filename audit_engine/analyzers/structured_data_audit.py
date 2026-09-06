"""Structured data coverage, correctness, and consistency checks.

Never reports "no structured data" as a single generic finding (spec section
10/16): every check here is scoped to a specific schema.org type against a
specific, quantified population of pages (e.g. "0/12 product pages"), and
distinguishes absent vs malformed vs incomplete vs contradicting-visible-content.
"""
from __future__ import annotations

from audit_engine.models import Evidence, SiteSnapshot
from audit_engine.parsing.html_extract import find_prices
from audit_engine.severity import FindingCandidate

_ORG_EXPECTED_PROPS = ("name", "url", "logo")
_PRODUCT_EXPECTED_PROPS = ("name", "offers")
_LOCALBUSINESS_HINTS = ("address", "location", "store", "hours", "directions")


def analyze(snapshot: SiteSnapshot, cfg) -> list[FindingCandidate]:
    ok_pages = snapshot.ok_pages()
    if not ok_pages:
        return []

    candidates: list[FindingCandidate] = []
    candidates += _check_organization(snapshot, ok_pages)
    candidates += _check_products(ok_pages)
    candidates += _check_localbusiness(ok_pages)
    candidates += _check_malformed(ok_pages)
    candidates += _check_visible_mismatch(ok_pages)
    candidates += _check_faq_opportunity(ok_pages)
    candidates += _check_breadcrumb_opportunity(ok_pages)
    return candidates


def _blocks_of_type(page, *type_names: str) -> list[dict]:
    wanted = {t.lower() for t in type_names}
    return [b for b in page.structured_data if wanted & {t.lower() for t in b.get("types", [])}]


def _check_organization(snapshot: SiteSnapshot, ok_pages: list) -> list[FindingCandidate]:
    home = next((p for p in ok_pages if p.page_role == "home"), ok_pages[0])
    org_blocks = _blocks_of_type(home, "Organization", "WebSite", "Corporation", "LocalBusiness")

    if not org_blocks:
        return [FindingCandidate(
            check_id="missing_organization_schema",
            evidence=[Evidence(
                source_url=home.url, signal="jsonld_organization_absent",
                observed_value="Homepage has no Organization/WebSite structured data block",
                expected_value="Organization or WebSite JSON-LD with name, url, logo, sameAs",
                confidence=0.9,
            )],
            scope=1.0, confidence=0.9,
            recommendation_summary="Add an Organization JSON-LD block to the homepage with the canonical "
                                    "brand name, official URL, logo, and sameAs links to authoritative "
                                    "external profiles (social, registries), matching the visible brand identity.",
        )]

    missing_props = [p for p in _ORG_EXPECTED_PROPS if not any(b["properties"].get(p) for b in org_blocks)]
    if missing_props:
        return [FindingCandidate(
            check_id="incomplete_structured_data",
            evidence=[Evidence(
                source_url=home.url, signal="jsonld_organization_incomplete",
                observed_value=f"Organization/WebSite structured data is missing: {', '.join(missing_props)}",
                expected_value=f"Properties present: {', '.join(_ORG_EXPECTED_PROPS)}",
                confidence=0.85,
            )],
            scope=1.0, confidence=0.85,
            recommendation_summary=f"Add the missing {', '.join(missing_props)} propert"
                                    f"{'y' if len(missing_props) == 1 else 'ies'} to the homepage's "
                                    "Organization structured data.",
        )]
    return []


def _check_products(ok_pages: list) -> list[FindingCandidate]:
    product_pages = [p for p in ok_pages if p.page_role == "product"]
    if len(product_pages) < 2:
        return []
    without_schema = [p for p in product_pages if not _blocks_of_type(p, "Product")]
    scope = len(without_schema) / len(product_pages)
    if scope == 0:
        return []
    confidence = 0.9 if len(product_pages) >= 3 else 0.7
    summary_text = (f"Crawled {len(product_pages)} product-role pages; "
                     f"{len(without_schema)}/{len(product_pages)} contain no Product/Offer JSON-LD")
    return [FindingCandidate(
        check_id="missing_product_schema",
        evidence=[Evidence(
            source_url=p.url, signal="jsonld_product_missing",
            observed_value=f"{summary_text} (this page: no Product/Offer block found)",
            expected_value="Product JSON-LD with name and an Offer (price, priceCurrency, availability)",
            confidence=confidence,
        ) for p in without_schema[:8]],
        scope=scope, confidence=confidence,
        recommendation_summary="Add Product/Offer JSON-LD to every product page, including name, "
                                "price, priceCurrency, and availability, matching the visible price/stock state.",
    )]


def _check_localbusiness(ok_pages: list) -> list[FindingCandidate]:
    location_signal_pages = [
        p for p in ok_pages
        if any(h in p.text.lower() for h in _LOCALBUSINESS_HINTS) or p.page_role == "contact"
    ]
    if not location_signal_pages:
        return []
    has_lb = any(_blocks_of_type(p, "LocalBusiness", "Store", "Organization") for p in ok_pages)
    if has_lb:
        return []
    return [FindingCandidate(
        check_id="missing_localbusiness_schema",
        evidence=[Evidence(
            source_url=p.url, signal="localbusiness_schema_absent",
            observed_value="Page text references a physical location/hours but no LocalBusiness "
                            "structured data was found anywhere on the crawled site",
            confidence=0.65,
        ) for p in location_signal_pages[:3]],
        scope=min(1.0, len(location_signal_pages) / len(ok_pages)), confidence=0.65,
        recommendation_summary="Add LocalBusiness JSON-LD (address, openingHours, telephone, geo) to "
                                "pages that describe a physical presence.",
    )]


def _check_malformed(ok_pages: list) -> list[FindingCandidate]:
    malformed_evidence = []
    for p in ok_pages:
        if p.render_delta and p.render_delta.notes and "did not parse" in p.render_delta.notes:
            malformed_evidence.append(Evidence(
                source_url=p.url, signal="jsonld_malformed",
                observed_value=p.render_delta.notes, confidence=0.95,
            ))
    if not malformed_evidence:
        return []
    return [FindingCandidate(
        check_id="malformed_structured_data",
        evidence=malformed_evidence[:8],
        scope=min(1.0, len(malformed_evidence) / len(ok_pages)), confidence=0.9,
        recommendation_summary="Fix invalid JSON syntax in the affected JSON-LD blocks (validate with "
                                "Google's Rich Results Test or the Schema.org validator before deploying).",
    )]


def _check_visible_mismatch(ok_pages: list) -> list[FindingCandidate]:
    """Compare a Product block's stated price against prices mentioned in visible text.
    Only flags when both are present and clearly disagree — never on absence alone."""
    mismatches = []
    for p in ok_pages:
        for block in _blocks_of_type(p, "Product"):
            offers = block["properties"].get("offers")
            price = None
            if isinstance(offers, dict):
                price = offers.get("price")
            elif isinstance(offers, list) and offers:
                price = offers[0].get("price") if isinstance(offers[0], dict) else None
            if not price:
                continue
            visible_prices = find_prices(p.text)
            normalized_visible = {v.strip("$€£ ").replace(",", "") for v in visible_prices}
            if visible_prices and str(price).replace(",", "") not in normalized_visible:
                mismatches.append(Evidence(
                    source_url=p.url, signal="structured_data_price_mismatch",
                    observed_value=f"JSON-LD price is {price}; visible text prices found: {', '.join(visible_prices[:3])}",
                    expected_value="Structured data price should match the visibly displayed price",
                    confidence=0.6,
                ))
    if not mismatches:
        return []
    return [FindingCandidate(
        check_id="structured_data_visible_mismatch",
        evidence=mismatches[:5],
        scope=min(1.0, len(mismatches) / max(len(ok_pages), 1)), confidence=0.6,
        recommendation_summary="Reconcile structured-data prices with the visibly displayed price on the "
                                "same page; a mismatch is a strong misinformation signal to AI agents that "
                                "trust structured data over rendered text.",
    )]


def _check_faq_opportunity(ok_pages: list) -> list[FindingCandidate]:
    """Proactive suggestion: pages that visibly present Q&A content but carry no FAQPage
    markup. Requires >=3 question-shaped headings on a single page — a couple of
    incidental '?' headings isn't a real FAQ section."""
    has_faq_schema = any(_blocks_of_type(p, "FAQPage") for p in ok_pages)
    if has_faq_schema:
        return []
    candidates = []
    for p in ok_pages:
        question_headings = [t for _, t in p.headings if t.strip().endswith("?")]
        if len(question_headings) >= 3:
            candidates.append((p, question_headings))
    if not candidates:
        return []
    return [FindingCandidate(
        check_id="missing_faq_schema_opportunity",
        evidence=[Evidence(
            source_url=p.url, signal="faq_shaped_content_unmarked",
            observed_value=f"{len(qs)} question-shaped headings found with no FAQPage structured data",
            confidence=0.7,
        ) for p, qs in candidates[:4]],
        scope=min(1.0, len(candidates) / len(ok_pages)), confidence=0.7,
        recommendation_summary="Mark up the existing question/answer content as FAQPage JSON-LD so AI "
                                "answer engines can cite it directly.",
        proactive=True,
    )]


def _check_breadcrumb_opportunity(ok_pages: list) -> list[FindingCandidate]:
    """Proactive suggestion: a real multi-level path hierarchy exists (e.g. /category/product)
    but no BreadcrumbList schema documents it anywhere."""
    has_breadcrumb_schema = any(_blocks_of_type(p, "BreadcrumbList") for p in ok_pages)
    if has_breadcrumb_schema:
        return []
    deep_pages = [p for p in ok_pages if p.url.rstrip("/").count("/") >= 4]  # scheme://host/a/b -> 2 segments deep
    if len(deep_pages) < 2:
        return []
    return [FindingCandidate(
        check_id="missing_breadcrumb_schema",
        evidence=[Evidence(
            source_url=p.url, signal="breadcrumb_schema_absent",
            observed_value="Multi-segment URL path implies a category hierarchy with no BreadcrumbList markup",
            confidence=0.6,
        ) for p in deep_pages[:4]],
        scope=min(1.0, len(deep_pages) / len(ok_pages)), confidence=0.6,
        recommendation_summary="Add BreadcrumbList JSON-LD reflecting the site's category/product "
                                "hierarchy on deep pages to make the navigational path machine-readable.",
        proactive=True,
    )]
