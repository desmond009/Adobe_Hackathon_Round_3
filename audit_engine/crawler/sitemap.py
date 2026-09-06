"""Sitemap discovery and parsing.

Checks robots.txt-declared sitemaps first, then falls back to /sitemap.xml.
Handles one level of sitemap-index nesting. Bounded by max_pages so a huge
sitemap can't blow the crawl budget; malformed XML degrades to an empty list
rather than raising (spec section 26: a single bad artifact must not crash
the audit).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def discover_sitemap_urls(
    root_url: str,
    robots_sitemaps: list[str],
    session: requests.Session,
    *,
    timeout_s: int,
    max_urls: int,
) -> list[str]:
    candidates = list(robots_sitemaps) or [root_url.rstrip("/") + "/sitemap.xml"]
    seen_sitemaps: set[str] = set()
    urls: list[str] = []

    for sitemap_url in candidates:
        if sitemap_url in seen_sitemaps or len(urls) >= max_urls:
            continue
        seen_sitemaps.add(sitemap_url)
        entries = _fetch_and_parse(sitemap_url, session, timeout_s)
        for kind, value in entries:
            if len(urls) >= max_urls:
                break
            if kind == "url":
                urls.append(value)
            elif kind == "sitemap" and value not in seen_sitemaps:
                seen_sitemaps.add(value)
                for sub_kind, sub_value in _fetch_and_parse(value, session, timeout_s):
                    if len(urls) >= max_urls:
                        break
                    if sub_kind == "url":
                        urls.append(sub_value)
    return urls[:max_urls]


def _fetch_and_parse(url: str, session: requests.Session, timeout_s: int) -> list[tuple[str, str]]:
    try:
        resp = session.get(url, timeout=timeout_s)
        if resp.status_code >= 400 or not resp.content:
            return []
        root = ET.fromstring(resp.content)
    except (requests.RequestException, ET.ParseError):
        return []

    tag = root.tag.lower()
    results: list[tuple[str, str]] = []
    if tag.endswith("sitemapindex"):
        for sm in root.findall("sm:sitemap/sm:loc", _NS):
            if sm.text:
                results.append(("sitemap", sm.text.strip()))
    elif tag.endswith("urlset"):
        for loc in root.findall("sm:url/sm:loc", _NS):
            if loc.text:
                results.append(("url", loc.text.strip()))
    return results
