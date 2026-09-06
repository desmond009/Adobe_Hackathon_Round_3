"""Shared organization-name-candidate extraction.

Both entity-identity-audit and freshness-corroboration-audit need "what does
this site call itself, and how consistently" — computed once here so the two
analyzers don't duplicate extraction logic or risk disagreeing on the raw
candidate set.

Fully deterministic: candidates come from <title>, og:site_name, JSON-LD
Organization/WebSite `name`, and footer copyright lines. No LLM involved in
*extraction*; only downstream *interpretation* of whether variants are
confusingly inconsistent may optionally involve the LLM layer.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from audit_engine.models import PageSnapshot

_COPYRIGHT_RE = re.compile(r"(?:©|\(c\)|copyright)\s*\d{0,4}\s*,?\s*([A-Z][A-Za-z0-9&.,'\- ]{1,60})", re.I)
_TITLE_SEPARATORS = re.compile(r"\s[|\-–—:]\s")


@dataclass
class EntityNameCandidate:
    name: str
    source_url: str
    source_signal: str  # "title" | "og:site_name" | "jsonld_organization" | "jsonld_website" | "copyright"


def extract_name_candidates(pages: list[PageSnapshot]) -> list[EntityNameCandidate]:
    candidates: list[EntityNameCandidate] = []

    for page in pages:
        if page.title:
            # The trailing segment after a separator is usually the brand ("Pricing | Acme Co").
            parts = _TITLE_SEPARATORS.split(page.title)
            if len(parts) > 1:
                candidates.append(EntityNameCandidate(parts[-1].strip(), page.url, "title"))

        site_name = page.meta.get("og:site_name")
        if site_name:
            candidates.append(EntityNameCandidate(site_name.strip(), page.url, "og:site_name"))

        for block in page.structured_data:
            types = {t.lower() for t in block.get("types", [])}
            name = block.get("properties", {}).get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            if "organization" in types:
                candidates.append(EntityNameCandidate(name.strip(), page.url, "jsonld_organization"))
            elif "website" in types:
                candidates.append(EntityNameCandidate(name.strip(), page.url, "jsonld_website"))

        match = _COPYRIGHT_RE.search(page.text[-400:] if len(page.text) > 400 else page.text)
        if match:
            candidates.append(EntityNameCandidate(match.group(1).strip().rstrip(".,"), page.url, "copyright"))

    return candidates


def normalize_name(name: str) -> str:
    """Loose normalization for grouping near-duplicate variants ("Acme, Inc." vs "acme inc")."""
    cleaned = re.sub(r"[^\w\s]", "", name.lower())
    cleaned = re.sub(r"\b(inc|llc|ltd|corp|corporation|co)\b", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def group_variants(candidates: list[EntityNameCandidate]) -> dict[str, list[EntityNameCandidate]]:
    groups: dict[str, list[EntityNameCandidate]] = {}
    for c in candidates:
        key = normalize_name(c.name)
        if not key:
            continue
        groups.setdefault(key, []).append(c)
    return groups


def dominant_name(candidates: list[EntityNameCandidate]) -> str | None:
    if not candidates:
        return None
    counts = Counter(c.name.strip() for c in candidates)
    return counts.most_common(1)[0][0]
