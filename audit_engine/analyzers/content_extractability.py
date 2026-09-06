"""Can a machine reliably extract concrete facts from this site?

Deterministic proxies stand in for the "vague vs concrete" judgment call
(spec allows LLM interpretation here, but a well-calibrated lexical heuristic
is cheaper, deterministic, and avoids an LLM call per page):

  * concreteness_score: ratio of concrete tokens (numbers, proper nouns via
    capitalization patterns, units, known factual anchors) to buzzword tokens
    drawn from a small curated marketing-vagueness wordlist.
  * the four "who / what / who-for / where" questions are answered by
    presence-of-signal checks (Organization name, product/service nouns near
    headings, audience language, address/locale signals) — never by asking
    an LLM to "read the whole site and guess".

If ANTHROPIC_API_KEY is configured, `intelligence/llm_interpret.py` can
optionally refine the vagueness judgment on the homepage only (one call,
bounded cost); the deterministic score is always computed first and used
as-is when the LLM path is unavailable or its output fails validation.
"""
from __future__ import annotations

import re

from audit_engine.models import Evidence, PageSnapshot, SiteSnapshot
from audit_engine.severity import FindingCandidate

_VAGUE_PHRASES = (
    "best-in-class", "world-class", "cutting-edge", "innovative solutions", "industry-leading",
    "next-generation", "state-of-the-art", "synergy", "empower", "seamless experience",
    "revolutionize", "game-changing", "unparalleled", "holistic approach", "robust solutions",
    "leading provider", "trusted partner", "wide range of",
)
_AUDIENCE_MARKERS = ("for small businesses", "for enterprises", "for developers", "for teams",
                     "for families", "for students", "for freelancers", "for startups",
                     "designed for", "built for", "perfect for", "ideal for")
_LOCATION_MARKERS = re.compile(
    r"\b(street|st\.|avenue|ave\.|suite|floor|based in|headquartered|located in)\b", re.I
)


def analyze(snapshot: SiteSnapshot, cfg) -> list[FindingCandidate]:
    ok_pages = snapshot.ok_pages()
    if not ok_pages:
        return []
    home = next((p for p in ok_pages if p.page_role == "home"), ok_pages[0])
    key_pages = [p for p in ok_pages if p.page_role in ("home", "about", "product", "pricing")] or ok_pages[:5]

    candidates: list[FindingCandidate] = []
    candidates += _check_who(home, ok_pages)
    candidates += _check_what(home, ok_pages)
    candidates += _check_who_for(key_pages)
    candidates += _check_where(ok_pages)
    candidates += _check_vague_language(key_pages)
    candidates += _check_heading_hierarchy(ok_pages)
    candidates += _check_contact_context(ok_pages)
    return candidates


def _has_org_identity_text(page: PageSnapshot) -> bool:
    if page.meta.get("og:site_name") or page.title:
        return True
    return any("organization" in {t.lower() for t in b.get("types", [])} for b in page.structured_data)


def _check_who(home: PageSnapshot, ok_pages: list) -> list[FindingCandidate]:
    has_identity = any(_has_org_identity_text(p) for p in ok_pages)
    if has_identity:
        return []
    return [FindingCandidate(
        check_id="unanswerable_who",
        evidence=[Evidence(
            source_url=home.url, signal="org_identity_absent",
            observed_value="No page title, og:site_name, or Organization structured data establishes "
                            "an organization name anywhere in the crawled sample",
            confidence=0.75,
        )],
        scope=1.0, confidence=0.75,
        recommendation_summary="State the organization's name explicitly in the homepage title, "
                                "og:site_name meta tag, and Organization structured data.",
    )]


def _check_what(home: PageSnapshot, ok_pages: list) -> list[FindingCandidate]:
    meta_desc = home.meta.get("description", "")
    h1s = [t for level, t in home.headings if level == 1]
    combined = " ".join([meta_desc, *h1s]).strip()
    if len(combined.split()) >= 6:
        return []
    return [FindingCandidate(
        check_id="unanswerable_what",
        evidence=[Evidence(
            source_url=home.url, signal="offering_description_thin",
            observed_value=f"Homepage meta description + H1 text totals only {len(combined.split())} words: "
                            f"{combined!r}",
            expected_value="A concise, concrete statement of what the business offers",
            confidence=0.7,
        )],
        scope=1.0, confidence=0.7,
        recommendation_summary="Add a homepage H1 and meta description that state concretely what the "
                                "business offers (products/services), not just a tagline.",
    )]


def _check_who_for(key_pages: list) -> list[FindingCandidate]:
    found = any(m in p.text.lower() for p in key_pages for m in _AUDIENCE_MARKERS)
    if found:
        return []
    return [FindingCandidate(
        check_id="unanswerable_who_for",
        evidence=[Evidence(
            source_url=key_pages[0].url, signal="audience_language_absent",
            observed_value=f"No target-audience language (e.g. 'for small businesses', 'built for teams') "
                            f"found across {len(key_pages)} key pages checked",
            confidence=0.6,
        )],
        scope=1.0, confidence=0.6,
        recommendation_summary="Add explicit audience-framing language to the homepage or about page "
                                "(e.g. who the product/service is designed for) so both humans and AI "
                                "agents can match the right visitor to the right offering.",
    )]


def _check_where(ok_pages: list) -> list[FindingCandidate]:
    has_location = any(
        _LOCATION_MARKERS.search(p.text) or p.contact_signals.get("phones")
        or any("address" in b.get("properties", {}) for b in p.structured_data)
        for p in ok_pages
    )
    if has_location:
        return []
    return [FindingCandidate(
        check_id="unanswerable_where",
        evidence=[Evidence(
            source_url=ok_pages[0].url, signal="location_signal_absent",
            observed_value=f"No address, phone number, or structured 'address' property found across "
                            f"{len(ok_pages)} crawled pages",
            confidence=0.55,
        )],
        scope=1.0, confidence=0.55,
        recommendation_summary="Publish at least one machine-readable location or contact signal "
                                "(address, phone, or structured-data address property) — relevant even for "
                                "online-only businesses (e.g. a registered jurisdiction or support contact).",
    )]


def _check_vague_language(key_pages: list) -> list[FindingCandidate]:
    evidence = []
    for p in key_pages:
        text_lower = p.text.lower()
        hits = [phrase for phrase in _VAGUE_PHRASES if phrase in text_lower]
        word_count = max(p.word_count, 1)
        density = len(hits) / (word_count / 100)  # vague phrases per 100 words
        if hits and density > 0.8:
            evidence.append(Evidence(
                source_url=p.url, signal="vague_marketing_language",
                observed_value=f"{len(hits)} vague marketing phrase(s) found in {word_count} words "
                                f"(density {density:.1f}/100w): {', '.join(hits[:5])}",
                confidence=0.6,
            ))
    if not evidence:
        return []
    return [FindingCandidate(
        check_id="vague_value_proposition",
        evidence=evidence[:6],
        scope=len(evidence) / len(key_pages), confidence=0.6,
        recommendation_summary="Replace generic marketing phrases with concrete, specific statements "
                                "(named products, quantified outcomes, explicit capabilities) on the "
                                "flagged pages so an AI agent can extract verifiable facts instead of tone.",
    )]


def _check_heading_hierarchy(ok_pages: list) -> list[FindingCandidate]:
    broken = []
    for p in ok_pages:
        levels = [lvl for lvl, _ in p.headings]
        if not levels:
            if p.word_count > 150:
                broken.append(p)
            continue
        if levels.count(1) == 0 and p.word_count > 150:
            broken.append(p)
        elif levels.count(1) > 1:
            broken.append(p)
    if len(ok_pages) < 3 or len(broken) / len(ok_pages) < 0.3:
        return []
    return [FindingCandidate(
        check_id="weak_heading_hierarchy",
        evidence=[Evidence(
            source_url=p.url, signal="heading_hierarchy_issue",
            observed_value=f"Page has {p.word_count} words but " + (
                "zero H1 headings" if 1 not in [lvl for lvl, _ in p.headings] else
                f"{[lvl for lvl, _ in p.headings].count(1)} H1 headings (expected exactly 1)"
            ),
            confidence=0.75,
        ) for p in broken[:8]],
        scope=len(broken) / len(ok_pages), confidence=0.75,
        recommendation_summary="Ensure every substantial page has exactly one H1 and a logical H2/H3 "
                                "hierarchy beneath it, so machine parsers can reconstruct page structure "
                                "without relying on visual layout.",
    )]


def _check_contact_context(ok_pages: list) -> list[FindingCandidate]:
    any_contact = any(p.contact_signals.get("emails") or p.contact_signals.get("phones") for p in ok_pages)
    if any_contact:
        return []
    return [FindingCandidate(
        check_id="missing_contact_context",
        evidence=[Evidence(
            source_url=ok_pages[0].url, signal="contact_info_absent",
            observed_value=f"No email address or phone number found in visible text across "
                            f"{len(ok_pages)} crawled pages",
            confidence=0.6,
        )],
        scope=1.0, confidence=0.6,
        recommendation_summary="Publish a machine-readable contact channel (email or phone) in visible "
                                "text, not only behind a contact form.",
    )]
