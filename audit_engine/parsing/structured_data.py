"""schema.org structured data extraction: JSON-LD, Microdata, and basic RDFa.

Normalizes every format into a common shape so downstream analyzers don't
need to know which markup format produced a given block:

    {"format": "json-ld" | "microdata" | "rdfa", "types": [...], "properties": {...}, "raw": <original>}

JSON-LD parsing is defensive: `@graph` arrays and top-level arrays are both
flattened to a list of individual typed blocks, and a block that fails to
parse is reported as a malformed-data signal rather than silently dropped —
the structured-data-audit analyzer needs to know markup was *attempted* and
broken, which is a materially different finding from markup being absent.
"""
from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag


def extract_structured_data(soup: BeautifulSoup) -> tuple[list[dict], list[str]]:
    """Returns (normalized_blocks, malformed_notes)."""
    blocks: list[dict] = []
    malformed: list[str] = []

    for i, script in enumerate(soup.find_all("script", attrs={"type": "application/ld+json"})):
        raw_text = script.string or script.get_text() or ""
        if not raw_text.strip():
            continue
        parsed = _parse_json_ld(raw_text)
        if parsed is None:
            malformed.append(f"json-ld block #{i} did not parse as valid JSON")
            continue
        blocks.extend(_flatten_json_ld(parsed))

    blocks.extend(_extract_microdata(soup))
    blocks.extend(_extract_rdfa(soup))
    return blocks, malformed


def _parse_json_ld(raw_text: str) -> Any:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    # Light, conservative repair: strip trailing commas before ] or } — a common
    # authoring mistake — and retry once. We do not attempt broader "fuzzy" repair;
    # anything else is genuinely malformed and should be reported as such.
    cleaned = re.sub(r",\s*([\]}])", r"\1", raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _flatten_json_ld(parsed: Any) -> list[dict]:
    nodes: list[Any] = []
    if isinstance(parsed, list):
        nodes = parsed
    elif isinstance(parsed, dict):
        if "@graph" in parsed and isinstance(parsed["@graph"], list):
            nodes = parsed["@graph"]
        else:
            nodes = [parsed]
    else:
        return []

    out = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        raw_type = node.get("@type", "Thing")
        types = raw_type if isinstance(raw_type, list) else [raw_type]
        properties = {k: v for k, v in node.items() if not k.startswith("@")}
        out.append({"format": "json-ld", "types": [str(t) for t in types], "properties": properties, "raw": node})
    return out


def _extract_microdata(soup: BeautifulSoup) -> list[dict]:
    out = []
    for scope in soup.find_all(attrs={"itemscope": True}):
        if not isinstance(scope, Tag):
            continue
        # Every itemscope (nested or not) becomes its own normalized block — a nested
        # scope (e.g. Product > Brand, Product > AggregateRating) is a real, separately
        # typed entity, not noise to discard. What we do guard against is attributing a
        # property to the wrong scope: each itemprop below is assigned only to its
        # *nearest* enclosing itemscope, so nesting never bleeds a child's properties
        # into its parent's block or vice versa.
        itemtype = scope.get("itemtype", "")
        types = [itemtype.rstrip("/").split("/")[-1]] if itemtype else ["Thing"]
        properties: dict[str, Any] = {}
        for prop_el in scope.find_all(attrs={"itemprop": True}):
            nearest_scope = prop_el.find_parent(attrs={"itemscope": True})
            if nearest_scope is not scope:
                continue  # belongs to a nested itemscope, not this one
            name = prop_el.get("itemprop")
            value = prop_el.get("content") or prop_el.get("href") or prop_el.get_text(strip=True)
            if name:
                properties[name] = value
        out.append({"format": "microdata", "types": types, "properties": properties, "raw": None})
    return out


def _extract_rdfa(soup: BeautifulSoup) -> list[dict]:
    """Best-effort RDFa support (typeof/property pairs). Complex RDFa (nested
    resources, vocab prefixes) is out of scope by design — documented as a
    known limitation rather than half-implemented silently."""
    out = []
    for scope in soup.find_all(attrs={"typeof": True}):
        if not isinstance(scope, Tag):
            continue
        types = [scope.get("typeof", "").split("/")[-1]]
        properties: dict[str, Any] = {}
        for prop_el in scope.find_all(attrs={"property": True}):
            name = prop_el.get("property")
            value = prop_el.get("content") or prop_el.get_text(strip=True)
            if name:
                properties[name] = value
        if types[0]:
            out.append({"format": "rdfa", "types": types, "properties": properties, "raw": None})
    return out
