"""SiteSnapshot <-> JSON (de)serialization.

Exists so the shared snapshot can cross a process boundary: the orchestrator
skill's crawl stage can persist one snapshot.json that every specialized
skill's standalone script then loads instead of re-crawling — the concrete
mechanism behind "skills consume the snapshot rather than re-crawling"
(spec section 24) when skills are invoked as separate agent tool calls
rather than through the single in-process `run_audit.py` pipeline.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from audit_engine.models import CrawlStats, PageSnapshot, RenderDelta, SiteSnapshot


def save_snapshot(snapshot: SiteSnapshot, path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(asdict(snapshot), fh)


def load_snapshot(path: str | Path) -> SiteSnapshot:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    pages = []
    for p in data["pages"]:
        render_delta = RenderDelta(**p["render_delta"]) if p.get("render_delta") else None
        p = {**p, "render_delta": render_delta, "headings": [tuple(h) for h in p.get("headings", [])]}
        pages.append(PageSnapshot(**p))

    data["pages"] = pages
    data["crawl_stats"] = CrawlStats(**data["crawl_stats"])
    return SiteSnapshot(**data)
