# Crawl / render checks

| check_id | Fires when | Minimum evidence required |
|---|---|---|
| `site_unreachable` | 0/N attempted pages fetched | crawl_stats shows zero ok pages |
| `robots_blocks_crawl` | robots.txt found and disallows the homepage | robots.txt fetched and parsed |
| `no_sitemap` | No sitemap via robots.txt `Sitemap:` or `/sitemap.xml` | sitemap discovery returned 0 URLs |
| `broken_internal_links` | >=1 internal link resolves to HTTP >=400 | >=3 internal links checked (status known) |
| `missing_canonical` | >=30% of sampled pages (of >=3) lack `<link rel=canonical>` | >=3 ok pages |
| `js_dependent_content` | Confirmed render-delta (>100 word gap, raw <50% of rendered), OR heuristic score >=0.75 AND raw word count <60 | see `render_heuristics.py` |

## js_dependency_score heuristic (0..1, four independent signals averaged)

1. A known SPA mount point (`#root`, `#app`, `#__next`, `#__nuxt`, `<app-root>`)
   exists and contains <15 words in the raw HTML.
2. Raw visible word count <40 with >=3 `<script>` tags present.
3. `<noscript>` fallback text is longer than half the visible body text (and
   >10 words) — a strong signal the real content only renders after JS runs.
4. Script byte volume is >60% of total HTML bytes while visible word count <150.

A page only needs a `js_dependency_score >= 0.5` to be *suspicious* (candidate
for a real render check); an actual finding requires the stronger bar above.
This is deliberately conservative — see spec section 8: never flag "uses
JavaScript" as a defect by itself.
