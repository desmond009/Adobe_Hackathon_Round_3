"""Raw-HTML-vs-rendered-DOM analysis.

Two-stage strategy (spec section 25):

  Stage 1 (always runs, free): static heuristics over the raw HTML estimate a
  `js_dependency_score` — no browser required. This alone is enough to decide
  whether a page is *suspicious*.

  Stage 2 (selective, optional): for the top-N suspicious/important pages,
  attempt a real Playwright render and compare word counts / structured-data
  counts before vs after execution. If Playwright (or its browser binaries)
  is not installed, this stage is skipped cleanly — the page's RenderDelta
  says `method="heuristic_only"` and the pipeline reports that limitation
  explicitly rather than asserting a render-gap it never actually measured.

This split means we never flag "every JS site" as broken (spec section 8):
a heuristic score alone only marks a page *suspicious*; an actual finding
requires either a confirmed render delta or multiple independent static
signals agreeing (see analyzers/crawl_render.py).
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from audit_engine.models import RenderDelta

_SPA_ROOT_IDS = ("root", "app", "__next", "__nuxt", "app-root")
_SPA_ROOT_TAGS = ("app-root", "app-shell")


def compute_js_dependency_score(html: str, soup: BeautifulSoup, word_count: int) -> float:
    """0..1 heuristic: higher means this page more likely depends on client-side
    JS execution to render its real content. Combines four independent, cheap
    signals so no single false trigger (e.g. a legitimately short page) dominates."""
    signals = []

    # Signal 1: a known SPA mount point exists and is nearly empty in the raw HTML.
    spa_root = None
    for tag_id in _SPA_ROOT_IDS:
        spa_root = soup.find(id=tag_id) or spa_root
    for tag_name in _SPA_ROOT_TAGS:
        spa_root = soup.find(tag_name) or spa_root
    if spa_root is not None:
        inner_words = len(spa_root.get_text(strip=True).split())
        signals.append(1.0 if inner_words < 15 else 0.0)
    else:
        signals.append(0.0)

    # Signal 2: very low visible word count despite a substantial page (many script tags / bytes).
    script_count = len(soup.find_all("script"))
    signals.append(1.0 if (word_count < 40 and script_count >= 3) else 0.0)

    # Signal 3: a <noscript> block carries meaningfully more content than the rendered body,
    # which typically means "please enable JavaScript" fallback content is the only static text.
    noscript_text = " ".join(t.get_text(strip=True) for t in soup.find_all("noscript"))
    signals.append(1.0 if len(noscript_text.split()) > max(word_count, 1) * 0.5 and len(noscript_text.split()) > 10 else 0.0)

    # Signal 4: script byte volume dwarfs visible text byte volume.
    script_bytes = sum(len(s.get_text()) for s in soup.find_all("script"))
    html_bytes = max(len(html), 1)
    signals.append(1.0 if script_bytes / html_bytes > 0.6 and word_count < 150 else 0.0)

    return sum(signals) / len(signals)


def heuristic_render_delta(html: str, soup: BeautifulSoup, word_count: int, structured_data_count: int) -> RenderDelta:
    score = compute_js_dependency_score(html, soup, word_count)
    return RenderDelta(
        method="heuristic_only",
        rendered=False,
        raw_word_count=word_count,
        raw_structured_data_count=structured_data_count,
        js_dependency_score=round(score, 2),
        notes="No headless browser available in this run; js_dependency_score is a static-HTML "
              "heuristic only, not a confirmed render gap.",
    )


def try_playwright_render(url: str, timeout_s: int) -> tuple[int, int] | None:
    """Best-effort real render. Returns (word_count, structured_data_script_count) or None
    if Playwright/its browsers are unavailable or the render fails for any reason.
    Never raises — a rendering failure degrades to 'unavailable', not a crash."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url, timeout=timeout_s * 1000, wait_until="networkidle")
            content = page.content()
            browser.close()
    except Exception:
        return None

    rendered_soup = BeautifulSoup(content, "lxml")
    for tag in rendered_soup(("script", "style", "noscript")):
        tag.decompose()
    text = re.sub(r"\s+", " ", rendered_soup.get_text(separator=" ", strip=True))
    word_count = len(text.split())
    sd_count = len(BeautifulSoup(content, "lxml").find_all("script", attrs={"type": "application/ld+json"}))
    return word_count, sd_count
