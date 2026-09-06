"""Freshness signals and cross-page fact consistency.

Distinguishes three evidence tiers explicitly (spec section 13):

  * observed on-site fact        -> reported normally
  * cross-page contradiction     -> reported as a distinct, higher-confidence finding
  * externally corroborated fact -> NOT implemented: this build has no outbound
    verification source wired in, and the spec is explicit that fabricating
    corroboration is worse than omitting it. `limitations` in the final report
    states this plainly rather than silently pretending the check ran.

Freshness itself is read from standard date signals only (article:published_time,
article:modified_time, JSON-LD datePublished/dateModified, a visible "Last
updated" string) — never inferred or guessed.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from audit_engine.models import Evidence, PageSnapshot, SiteSnapshot
from audit_engine.severity import FindingCandidate

_DATE_META_KEYS = ("article:modified_time", "article:published_time", "og:updated_time", "date", "last-modified")
_VISIBLE_DATE_RE = re.compile(
    r"(?:last updated|updated on|published on|as of)\s*[:\-]?\s*"
    r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.I,
)
_STALE_THRESHOLD_DAYS = 730  # ~2 years, a generous generic bound (not domain-specific)


def analyze(snapshot: SiteSnapshot, cfg) -> list[FindingCandidate]:
    ok_pages = snapshot.ok_pages()
    if not ok_pages:
        return []

    candidates: list[FindingCandidate] = []
    candidates += _check_freshness_signals(ok_pages)
    candidates += _check_stale_content(ok_pages)
    candidates += _check_contact_info_consistency(ok_pages)
    return candidates


def _extract_date(page: PageSnapshot) -> datetime | None:
    for key in _DATE_META_KEYS:
        if key in page.meta:
            dt = _parse_date(page.meta[key])
            if dt:
                return dt
    for block in page.structured_data:
        for prop in ("dateModified", "datePublished"):
            val = block.get("properties", {}).get(prop)
            if isinstance(val, str):
                dt = _parse_date(val)
                if dt:
                    return dt
    match = _VISIBLE_DATE_RE.search(page.text)
    if match:
        return _parse_date(match.group(1))
    return None


def _parse_date(raw: str) -> datetime | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            dt = datetime.strptime(raw[:len(fmt) + 6] if "%z" in fmt else raw, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _check_freshness_signals(ok_pages: list) -> list[FindingCandidate]:
    time_sensitive = [p for p in ok_pages if p.page_role in ("pricing", "product", "faq")]
    if len(time_sensitive) < 2:
        return []
    without_date = [p for p in time_sensitive if _extract_date(p) is None]
    scope = len(without_date) / len(time_sensitive)
    if scope < 0.5:
        return []
    return [FindingCandidate(
        check_id="no_freshness_signal",
        evidence=[Evidence(
            source_url=p.url, signal="freshness_date_absent",
            observed_value="No publication/modification date signal found on this time-sensitive page",
            confidence=0.6,
        ) for p in without_date[:6]],
        scope=scope, confidence=0.6,
        recommendation_summary="Add dateModified (JSON-LD) or a visible 'last updated' timestamp to "
                                "pricing/product/FAQ pages so AI agents can judge how current the "
                                "information is before relying on it.",
    )]


def _check_stale_content(ok_pages: list) -> list[FindingCandidate]:
    now = datetime.now(timezone.utc)
    stale = []
    for p in ok_pages:
        dt = _extract_date(p)
        if dt and (now - dt).days > _STALE_THRESHOLD_DAYS:
            stale.append((p, (now - dt).days))
    if not stale:
        return []
    return [FindingCandidate(
        check_id="stale_content_signal",
        evidence=[Evidence(
            source_url=p.url, signal="stale_modification_date",
            observed_value=f"Last modification signal is {days} days old (> {_STALE_THRESHOLD_DAYS}-day threshold)",
            confidence=0.7,
        ) for p, days in stale[:6]],
        scope=min(1.0, len(stale) / len(ok_pages)), confidence=0.7,
        recommendation_summary="Review and refresh the flagged pages' content, then update their "
                                "dateModified/last-updated signal to reflect the actual review date.",
    )]


def _check_contact_info_consistency(ok_pages: list) -> list[FindingCandidate]:
    """Cross-page contact-fact consistency: if two or more pages each publish a phone
    number, but the numbers disagree, that's a concrete, low-false-positive signal of
    outdated or unreconciled contact information (spec section 13's "internal
    contradictions" check). A single page with a number, or all pages agreeing, is
    not evidence of anything and is not flagged."""
    phone_by_page = {p.url: set(p.contact_signals.get("phones", [])) for p in ok_pages if p.contact_signals.get("phones")}
    if len(phone_by_page) < 2:
        return []

    all_numbers = set().union(*phone_by_page.values())
    if len(all_numbers) <= 1:
        return []  # every page that lists a phone number agrees

    evidence = [
        Evidence(
            source_url=url, signal="phone_number_disagreement",
            observed_value=f"Page lists phone number(s): {', '.join(sorted(numbers))}",
            expected_value="A single consistent phone number across all pages",
            confidence=0.65,
        )
        for url, numbers in list(phone_by_page.items())[:6]
    ]
    return [FindingCandidate(
        check_id="outdated_contact_info_pattern",
        evidence=evidence,
        scope=min(1.0, len(phone_by_page) / len(ok_pages)), confidence=0.65,
        recommendation_summary="Reconcile phone numbers shown across pages to a single current number, "
                                "or clearly label region/department-specific numbers so the difference "
                                "isn't mistaken for stale information.",
    )]
