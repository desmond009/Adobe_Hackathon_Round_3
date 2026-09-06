"""On-site engagement: orientation, next-action, and internal-linking friction.

Every check here is link-graph/text-structure based, computed from the shared
snapshot's already-extracted headings/links/text — no additional crawling,
no "does this look nice" subjective judgment.
"""
from __future__ import annotations

import re

from audit_engine.models import Evidence, SiteSnapshot
from audit_engine.severity import FindingCandidate

_CTA_PATTERNS = re.compile(
    r"\b(sign up|get started|book (?:a|now)|contact us|request a demo|buy now|add to cart|"
    r"learn more|subscribe|start (?:your|a) (?:free )?trial|schedule|talk to (?:us|sales)|download)\b",
    re.I,
)


def analyze(snapshot: SiteSnapshot, cfg) -> list[FindingCandidate]:
    ok_pages = snapshot.ok_pages()
    if not ok_pages:
        return []

    candidates: list[FindingCandidate] = []
    candidates += _check_homepage_orientation(ok_pages)
    candidates += _check_next_action(ok_pages)
    candidates += _check_dead_ends(ok_pages)
    candidates += _check_thin_internal_linking(ok_pages)
    return candidates


def _check_homepage_orientation(ok_pages: list) -> list[FindingCandidate]:
    home = next((p for p in ok_pages if p.page_role == "home"), None)
    if home is None:
        return []
    h1s = [t for lvl, t in home.headings if lvl == 1]
    first_block = " ".join(h1s) or home.meta.get("description", "")
    if len(first_block.split()) >= 5:
        return []
    return [FindingCandidate(
        check_id="missing_value_proposition_orientation",
        evidence=[Evidence(
            source_url=home.url, signal="orientation_text_thin",
            observed_value=f"Homepage's H1/description content is only {len(first_block.split())} words: "
                            f"{first_block!r}",
            expected_value="A clear statement of what the business does, visible immediately",
            confidence=0.65,
        )],
        scope=1.0, confidence=0.65,
        recommendation_summary="Give the homepage a clear, concrete H1 (and supporting sentence) that "
                                "tells a first-time visitor what the business does within the first "
                                "screen of content.",
    )]


def _check_next_action(ok_pages: list) -> list[FindingCandidate]:
    key_pages = [p for p in ok_pages if p.page_role in ("home", "product", "pricing")] or ok_pages[:5]
    without_cta = [p for p in key_pages if not _CTA_PATTERNS.search(p.text)]
    if not without_cta:
        return []
    scope = len(without_cta) / len(key_pages)
    if scope < 0.4:
        return []
    return [FindingCandidate(
        check_id="no_clear_next_action",
        evidence=[Evidence(
            source_url=p.url, signal="cta_absent",
            observed_value="No recognizable call-to-action phrase found in visible text "
                            f"(role: {p.page_role})",
            confidence=0.55,
        ) for p in without_cta[:6]],
        scope=scope, confidence=0.55,
        recommendation_summary="Add an explicit next-action prompt (e.g. 'Get started', 'Contact us', "
                                "'Request a demo') to the flagged pages so visitors and agentic browsers "
                                "have an unambiguous path forward.",
    )]


def _check_dead_ends(ok_pages: list) -> list[FindingCandidate]:
    dead_ends = [p for p in ok_pages if not p.links_internal and p.word_count > 30]
    if len(ok_pages) < 4 or not dead_ends:
        return []
    scope = len(dead_ends) / len(ok_pages)
    if scope < 0.15:
        return []
    return [FindingCandidate(
        check_id="dead_end_page",
        evidence=[Evidence(
            source_url=p.url, signal="no_outgoing_internal_links",
            observed_value="Page has zero internal links to other pages on the site",
            confidence=0.8,
        ) for p in dead_ends[:6]],
        scope=scope, confidence=0.8,
        recommendation_summary="Add contextual internal links (related content, navigation, or a footer "
                                "sitemap) to the flagged pages so visitors and crawlers can continue "
                                "exploring the site from them.",
    )]


def _check_thin_internal_linking(ok_pages: list) -> list[FindingCandidate]:
    if len(ok_pages) < 5:
        return []
    inbound_counts: dict[str, int] = {p.url: 0 for p in ok_pages}
    for p in ok_pages:
        for link in set(p.links_internal):
            if link in inbound_counts:
                inbound_counts[link] += 1
    key_pages = [p for p in ok_pages if p.page_role in ("product", "pricing")]
    weakly_linked = [p for p in key_pages if inbound_counts.get(p.url, 0) <= 1]
    if not key_pages or len(weakly_linked) / len(key_pages) < 0.4:
        return []
    return [FindingCandidate(
        check_id="thin_internal_linking",
        evidence=[Evidence(
            source_url=p.url, signal="low_inbound_internal_links",
            observed_value=f"Only {inbound_counts.get(p.url, 0)} other crawled page(s) link to this page",
            expected_value="Important pages should be reachable from multiple contextual entry points",
            confidence=0.55,
        ) for p in weakly_linked[:6]],
        scope=len(weakly_linked) / len(key_pages), confidence=0.55,
        recommendation_summary="Strengthen internal linking to product/pricing pages from related content "
                                "(navigation, category pages, blog posts) so context is preserved as "
                                "visitors and agents navigate between related pages.",
    )]
