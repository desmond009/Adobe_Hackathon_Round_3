"""Bounded, priority-ordered site crawl -> SiteSnapshot.

Not a naive BFS: URLs are scored and popped in priority order so that, within
a small MAX_PAGES budget, the sample still covers the pages that carry
identity/commerce signal (about, contact, pricing, product...) rather than
whatever the BFS frontier happens to reach first on a large site. This is the
"Crawl planning" step from the pipeline diagram.

Concurrency is a small bounded thread pool (requests is blocking); a single
page's failure is caught and recorded as a non-ok PageSnapshot, never raised
(spec section 7/26).
"""
from __future__ import annotations

import heapq
import itertools
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone

from audit_engine.crawler.fetcher import build_session, fetch
from audit_engine.crawler.robots import RobotsInfo, fetch_robots
from audit_engine.crawler.sitemap import discover_sitemap_urls
from audit_engine.crawler.url_utils import is_same_site, normalize_url, url_depth_hint
from audit_engine.models import CrawlStats, PageSnapshot, RenderDelta, SiteSnapshot
from audit_engine.parsing.html_extract import parse_page
from audit_engine.parsing.render_heuristics import compute_js_dependency_score
from audit_engine.parsing.structured_data import extract_structured_data


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _priority(url: str, seed_url: str, depth: int, keywords: list[str], from_sitemap: bool) -> float:
    """Lower score = crawled sooner. Homepage and sitemap-listed / keyword-matched
    URLs are pulled forward; deep, unlabeled paths sink to the back of the queue."""
    score = float(depth) * 10
    path = url.lower()
    if url.rstrip("/") == seed_url.rstrip("/"):
        score -= 100
    if from_sitemap:
        score -= 5
    if any(kw in path for kw in keywords):
        score -= 8
    score += url_depth_hint(url, seed_url) * 0.5
    return score


def crawl_site(seed_url: str, cfg) -> SiteSnapshot:
    crawl_cfg = cfg.section("crawl")
    max_pages = crawl_cfg.get("max_pages", 25)
    max_depth = crawl_cfg.get("max_depth", 3)
    concurrency = crawl_cfg.get("concurrency", 5)
    timeout_s = crawl_cfg.get("request_timeout_s", 10)
    overall_budget_s = crawl_cfg.get("overall_budget_s", 150)
    max_response_size = crawl_cfg.get("max_response_size_bytes", 2_000_000)
    max_redirects = crawl_cfg.get("max_redirects", 5)
    user_agent = crawl_cfg.get("user_agent", "AdobeBrandAIReadinessAuditBot/1.0")
    allowed_content_types = crawl_cfg.get("allowed_content_types", ["text/html"])
    tracking_params = crawl_cfg.get("tracking_params", [])
    priority_keywords = crawl_cfg.get("priority_keywords", [])
    respect_robots = crawl_cfg.get("respect_robots_txt", True)

    started_at = _now_iso()
    t0 = time.monotonic()
    session = build_session(user_agent)

    root_url = normalize_url(seed_url)
    # Hostname only, no port: is_same_site() compares registrable domains derived by
    # splitting on ".", so a lingering ":port" here would silently fail every
    # same-site comparison whenever the seed URL carries a non-default port (e.g. a
    # local test server) — real sites on 80/443 never surface this since normalize_url
    # already strips those default ports.
    seed_host = root_url.split("/")[2].split(":")[0]

    robots = fetch_robots(root_url, user_agent, timeout_s) if respect_robots else RobotsInfo(found=False, allowed_root=True)
    sitemap_urls = discover_sitemap_urls(root_url, robots.sitemap_urls, session, timeout_s=timeout_s, max_urls=max_pages * 3)

    stats = CrawlStats(urls_discovered=1 + len(sitemap_urls))
    visited: set[str] = set()
    pages: list[PageSnapshot] = []

    frontier: list[tuple[float, int, int, str]] = []
    counter = itertools.count()
    heapq.heappush(frontier, (_priority(root_url, root_url, 0, priority_keywords, False), 0, next(counter), root_url))
    for su in sitemap_urls:
        norm = normalize_url(su)
        if is_same_site(norm, seed_host):
            heapq.heappush(frontier, (_priority(norm, root_url, 1, priority_keywords, True), 1, next(counter), norm))

    stopped_reason = "completed"

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        in_flight: dict = {}
        while frontier or in_flight:
            if time.monotonic() - t0 > overall_budget_s:
                stopped_reason = "time_budget"
                break
            if len(pages) >= max_pages and not in_flight:
                stopped_reason = "max_pages"
                break

            while frontier and len(in_flight) < concurrency and (len(pages) + len(in_flight)) < max_pages:
                _, depth, _, url = heapq.heappop(frontier)
                if url in visited:
                    continue
                visited.add(url)
                if respect_robots and not robots.is_allowed(url, user_agent):
                    stats.pages_skipped_robots += 1
                    continue
                future = pool.submit(
                    fetch, session, url,
                    timeout_s=timeout_s, max_response_size_bytes=max_response_size,
                    max_redirects=max_redirects, allowed_content_types=allowed_content_types,
                )
                in_flight[future] = (url, depth)

            if not in_flight:
                if not frontier:
                    stopped_reason = "no_more_urls"
                break

            # Wait for at least one in-flight fetch to finish, then drain every future
            # that's done — never let one hung socket (beyond its own request timeout)
            # block the whole crawl loop past our own wait ceiling.
            done_set, _pending = wait(list(in_flight.keys()), timeout=timeout_s + 5, return_when=FIRST_COMPLETED)
            done = list(done_set) if done_set else []

            for future in done:
                url, depth = in_flight.pop(future)
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - a single page must never crash the crawl
                    pages.append(_error_page(url, depth, f"fetch_exception: {exc}"))
                    stats.pages_failed += 1
                    continue

                page, discovered = _build_page_snapshot(result, depth, root_url)
                pages.append(page)
                if page.ok:
                    stats.pages_fetched += 1
                else:
                    stats.pages_failed += 1

                if depth < max_depth:
                    for link in discovered:
                        if link not in visited and is_same_site(link, seed_host):
                            heapq.heappush(
                                frontier,
                                (_priority(link, root_url, depth + 1, priority_keywords, False), depth + 1, next(counter), link),
                            )
                            stats.urls_discovered += 1

    stats.duration_s = round(time.monotonic() - t0, 2)
    stats.stopped_reason = stopped_reason

    return SiteSnapshot(
        domain=seed_host,
        root_url=root_url,
        robots_txt_found=robots.found,
        robots_allowed_root=robots.allowed_root,
        robots_disallow_rules=robots.disallow_rules,
        sitemap_urls=sitemap_urls,
        pages=pages,
        crawl_started_at=started_at,
        crawl_finished_at=_now_iso(),
        crawl_stats=stats,
    )


def _error_page(url: str, depth: int, error: str) -> PageSnapshot:
    return PageSnapshot(url=url, final_url=url, depth=depth, status=None, ok=False, error=error,
                         content_type=None, fetched_at=_now_iso())


def _build_page_snapshot(result, depth: int, root_url: str) -> tuple[PageSnapshot, list[str]]:
    if not result.ok or not result.text:
        return (
            PageSnapshot(
                url=result.url, final_url=result.final_url, depth=depth, status=result.status,
                ok=False, error=result.error, content_type=result.content_type,
                headers=result.headers, fetched_at=_now_iso(),
            ),
            [],
        )

    parsed = parse_page(result.text, result.final_url)
    soup = parsed.pop("soup")
    structured_data, malformed_notes = extract_structured_data(soup)
    js_score = compute_js_dependency_score(result.text, soup, parsed["word_count"])

    page = PageSnapshot(
        url=result.url,
        final_url=result.final_url,
        depth=depth,
        status=result.status,
        ok=True,
        error=None,
        content_type=result.content_type,
        headers=result.headers,
        fetched_at=_now_iso(),
        raw_html=result.text if len(result.text) < 500_000 else result.text[:500_000],
        text=parsed["text"],
        word_count=parsed["word_count"],
        title=parsed["title"],
        meta=parsed["meta"],
        headings=parsed["headings"],
        links_internal=parsed["links_internal"],
        links_external=parsed["links_external"],
        canonical=parsed["canonical"],
        lang=parsed["lang"],
        structured_data=structured_data,
        contact_signals=parsed["contact_signals"],
        render_delta=RenderDelta(
            method="heuristic_only", rendered=False, raw_word_count=parsed["word_count"],
            raw_structured_data_count=len(structured_data), js_dependency_score=round(js_score, 2),
            notes="; ".join(malformed_notes) if malformed_notes else "",
        ),
        page_role=parsed["page_role"],
    )
    return page, parsed["links_internal"]
