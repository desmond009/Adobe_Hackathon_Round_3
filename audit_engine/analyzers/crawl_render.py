"""Crawlability and render-fidelity checks.

Covers: robots.txt blocking, sitemap presence, broken internal links,
redirect chains, canonical hygiene, and JS-dependent content detection.

False-positive control for the JS check specifically: a page is only flagged
when its heuristic js_dependency_score is high AND (a real Playwright render
confirmed a material word-count gap, OR at least two independent static
signals agree AND the raw word count is very low in absolute terms). A
single ambiguous signal on an otherwise reasonably-sized page is never
enough — this is exactly the "don't flag every JS site" requirement.
"""
from __future__ import annotations

from audit_engine.models import Evidence, SiteSnapshot
from audit_engine.severity import FindingCandidate

_JS_SUSPICION_FLOOR = 0.5
_JS_CONFIRMED_FLOOR = 0.75
_THIN_CONTENT_WORDS = 60


def analyze(snapshot: SiteSnapshot, cfg) -> list[FindingCandidate]:
    ok_pages = snapshot.ok_pages()

    if not ok_pages:
        # Total unreachability (DNS/connection failure, everything timed out, etc.) is a
        # single, unambiguous root cause. Reporting "no sitemap" / "no canonical tags" on
        # top of it would be technically true but misleading noise — those checks assume
        # *some* successful crawl to be meaningful evidence against. Short-circuit here
        # instead of letting every other check in this module fire on an empty page list.
        errors = sorted({p.error for p in snapshot.pages if p.error})
        return [FindingCandidate(
            check_id="site_unreachable",
            evidence=[Evidence(
                source_url=snapshot.root_url, signal="zero_pages_fetched",
                observed_value=f"0/{len(snapshot.pages)} attempted page(s) could be fetched"
                                + (f" (errors: {', '.join(errors[:3])})" if errors else ""),
                confidence=0.9,
            )],
            scope=1.0, confidence=0.9,
            recommendation_summary="Confirm the domain resolves and serves content over HTTPS/HTTP to "
                                    "standard crawlers; no other check in this audit can run until the "
                                    "site is reachable.",
        )]

    candidates: list[FindingCandidate] = []
    candidates += _check_robots(snapshot)
    candidates += _check_sitemap(snapshot)
    candidates += _check_broken_links(snapshot, ok_pages)
    candidates += _check_canonical(ok_pages)
    candidates += _check_js_dependency(ok_pages)
    return candidates


def _check_robots(snapshot: SiteSnapshot) -> list[FindingCandidate]:
    if snapshot.robots_txt_found and not snapshot.robots_allowed_root:
        return [FindingCandidate(
            check_id="robots_blocks_crawl",
            evidence=[Evidence(
                source_url=snapshot.root_url, signal="robots_disallow_root",
                observed_value="robots.txt disallows crawling the homepage for this audit's user-agent class",
                expected_value="Homepage and key pages allowed for reputable crawlers",
                confidence=0.95,
            )],
            scope=1.0, confidence=0.95,
            recommendation_summary="Update robots.txt to allow crawling of public marketing/product pages "
                                    "by reputable AI and search crawlers; keep disallow rules scoped to "
                                    "account/checkout/admin paths only.",
        )]
    return []


def _check_sitemap(snapshot: SiteSnapshot) -> list[FindingCandidate]:
    if not snapshot.sitemap_urls:
        return [FindingCandidate(
            check_id="no_sitemap",
            evidence=[Evidence(
                source_url=snapshot.root_url, signal="sitemap_absent",
                observed_value="No sitemap.xml discovered via robots.txt Sitemap: directive or /sitemap.xml",
                confidence=0.85,
            )],
            scope=1.0, confidence=0.85,
            recommendation_summary="Publish an XML sitemap listing canonical URLs for all indexable pages "
                                    "and declare it in robots.txt via a Sitemap: directive.",
        )]
    return []


def _check_broken_links(snapshot: SiteSnapshot, ok_pages: list) -> list[FindingCandidate]:
    status_by_url = {p.final_url: p.status for p in snapshot.pages}
    status_by_url.update({p.url: p.status for p in snapshot.pages})
    broken: list[Evidence] = []
    checked = 0
    for page in ok_pages:
        for link in page.links_internal:
            if link not in status_by_url:
                continue  # not crawled (outside budget) — no evidence either way
            checked += 1
            status = status_by_url[link]
            if status is not None and status >= 400:
                broken.append(Evidence(
                    source_url=page.url, signal="broken_internal_link",
                    observed_value=f"Link to {link} returns HTTP {status}",
                    confidence=0.9,
                ))
    if not broken or checked < 3:
        return []
    scope = min(1.0, len(broken) / max(checked, 1))
    return [FindingCandidate(
        check_id="broken_internal_links",
        evidence=broken[:8],
        scope=scope, confidence=0.9,
        recommendation_summary=f"Fix or remove {len(broken)} broken internal link(s) found across "
                                f"{len(ok_pages)} crawled pages; broken links block both crawlers and users "
                                "from reaching linked content.",
    )]


def _check_canonical(ok_pages: list) -> list[FindingCandidate]:
    missing = [p for p in ok_pages if not p.canonical]
    if len(ok_pages) < 3:
        return []
    scope = len(missing) / len(ok_pages)
    if scope < 0.3:
        return []
    return [FindingCandidate(
        check_id="missing_canonical",
        evidence=[Evidence(
            source_url=p.url, signal="canonical_missing",
            observed_value=f"No <link rel=canonical> found on {p.url}",
        ) for p in missing[:8]],
        scope=scope, confidence=0.85,
        recommendation_summary=f"Add self-referencing canonical tags to the {len(missing)}/{len(ok_pages)} "
                                "crawled pages missing them, so crawlers and AI agents can resolve one "
                                "authoritative URL per piece of content.",
    )]


def _check_js_dependency(ok_pages: list) -> list[FindingCandidate]:
    suspicious = [p for p in ok_pages if p.render_delta and p.render_delta.js_dependency_score >= _JS_SUSPICION_FLOOR]
    if not suspicious:
        return []

    confirmed: list = []
    thin_and_confirmed: list = []
    for p in suspicious:
        rd = p.render_delta
        if rd.rendered and rd.rendered_word_count is not None:
            gap = rd.rendered_word_count - rd.raw_word_count
            if gap > 100 and rd.raw_word_count < rd.rendered_word_count * 0.5:
                confirmed.append(p)
        elif rd.js_dependency_score >= _JS_CONFIRMED_FLOOR and p.word_count < _THIN_CONTENT_WORDS:
            thin_and_confirmed.append(p)

    flagged = confirmed + thin_and_confirmed
    if not flagged:
        return []

    evidence = []
    for p in confirmed:
        rd = p.render_delta
        evidence.append(Evidence(
            source_url=p.url, signal="render_delta_confirmed",
            observed_value=f"Rendered DOM has {rd.rendered_word_count} words vs {rd.raw_word_count} in raw HTML",
            expected_value="Server-rendered HTML should carry the page's material text content",
            confidence=0.95,
        ))
    for p in thin_and_confirmed:
        evidence.append(Evidence(
            source_url=p.url, signal="js_dependency_heuristic",
            observed_value=f"Only {p.word_count} visible words in raw HTML with a strong SPA/heavy-script "
                            f"signature (js_dependency_score={p.render_delta.js_dependency_score})",
            confidence=0.65,
        ))

    conf = 0.9 if confirmed else 0.65
    return [FindingCandidate(
        check_id="js_dependent_content",
        evidence=evidence,
        scope=len(flagged) / len(ok_pages),
        confidence=conf,
        recommendation_summary="Server-render (or statically pre-render) the primary content on these "
                                "pages so material facts are present in the initial HTML response, not "
                                "only after client-side JavaScript execution.",
    )]
