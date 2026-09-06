"""Deterministic HTML -> structured page facts.

Every field here is computed with plain parsing/regex, never an LLM — per the
"deterministic checks first" principle, this is the boundary that turns raw
bytes into the Evidence-grade facts analyzers reason over.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from audit_engine.crawler.url_utils import is_same_site, normalize_url

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s.\-]?)?\(?\d{2,4}\)?[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}")
_PRICE_RE = re.compile(r"(?:[$€£¥]\s?\d[\d,]*(?:\.\d{2})?)|(?:\d[\d,]*(?:\.\d{2})?\s?(?:USD|EUR|GBP))")

_BOILERPLATE_TAGS = ("script", "style", "noscript", "template", "svg")

_ROLE_KEYWORDS = {
    "home": ("", "/", "/home", "/index"),
    "about": ("about", "company", "our-story", "who-we-are"),
    "contact": ("contact", "contact-us", "support"),
    "pricing": ("pricing", "plans", "price"),
    "product": ("product", "products", "shop", "store", "item"),
    "faq": ("faq", "faqs", "help"),
}


def parse_page(html: str, url: str) -> dict:
    """Parse one page's HTML into the fields PageSnapshot needs. Returns a dict
    (rather than the dataclass directly) so callers can layer in crawl-time
    fields like depth/status before constructing PageSnapshot."""
    soup = BeautifulSoup(html, "lxml")

    title = _text_or_none(soup.title)
    meta = _extract_meta(soup)
    canonical_tag = soup.find("link", rel=lambda v: v and "canonical" in v)
    canonical = normalize_url(canonical_tag["href"], base=url) if canonical_tag and canonical_tag.get("href") else None
    lang = (soup.html.get("lang") if soup.html else None)

    headings = [
        (int(h.name[1]), h.get_text(strip=True))
        for h in soup.find_all(re.compile(r"^h[1-6]$"))
        if h.get_text(strip=True)
    ]

    visible_text = _visible_text(soup)
    word_count = len(visible_text.split())

    links_internal, links_external = _extract_links(soup, url)

    contact_signals = {
        "emails": sorted(set(_EMAIL_RE.findall(visible_text)))[:10],
        "phones": sorted(set(m.strip() for m in _PHONE_RE.findall(visible_text) if len(re.sub(r"\D", "", m)) >= 7))[:10],
    }

    return {
        "title": title,
        "meta": meta,
        "canonical": canonical,
        "lang": lang,
        "headings": headings,
        "text": visible_text,
        "word_count": word_count,
        "links_internal": links_internal,
        "links_external": links_external,
        "contact_signals": contact_signals,
        "page_role": _infer_page_role(url),
        "soup": soup,  # retained transiently for structured-data extraction; not stored on PageSnapshot
    }


def _text_or_none(tag) -> str | None:
    if tag is None:
        return None
    text = tag.get_text(strip=True)
    return text or None


def _extract_meta(soup: BeautifulSoup) -> dict[str, str]:
    meta: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        key = tag.get("name") or tag.get("property")
        content = tag.get("content")
        if key and content:
            meta[key.lower()] = content
    return meta


def _visible_text(soup: BeautifulSoup) -> str:
    clone = BeautifulSoup(str(soup), "lxml")
    for tag in clone(_BOILERPLATE_TAGS):
        tag.decompose()
    for hidden in clone.find_all(style=re.compile(r"display:\s*none|visibility:\s*hidden", re.I)):
        hidden.decompose()
    for hidden in clone.find_all(attrs={"aria-hidden": "true"}):
        hidden.decompose()
    text = clone.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _extract_links(soup: BeautifulSoup, page_url: str) -> tuple[list[str], list[str]]:
    seed_host = urlparse(page_url).netloc
    internal, external = [], []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        normalized = normalize_url(href, base=page_url)
        if normalized in seen:
            continue
        seen.add(normalized)
        (internal if is_same_site(normalized, seed_host) else external).append(normalized)
    return internal, external


def _infer_page_role(url: str) -> str:
    path = urlparse(url).path.strip("/").lower()
    for role, keywords in _ROLE_KEYWORDS.items():
        if path in keywords or any(path.startswith(k + "/") or f"/{k}" in path or path == k for k in keywords if k):
            return role
    return "other"


def find_prices(text: str) -> list[str]:
    return list(dict.fromkeys(_PRICE_RE.findall(text)))[:20]
