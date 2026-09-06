---
name: crawl-render-audit
description: Audits crawlability and render fidelity for a website - robots.txt restrictions, sitemap presence, canonical tag hygiene, broken internal links, and whether important content is materially harder to extract without executing JavaScript. Use as part of the audit-orchestrator pipeline, or standalone to check whether a specific site can be reliably crawled and parsed by AI agents and search/answer engines.
allowed-tools: ["Bash", "Read"]
metadata:
  category: crawlability
  version: "1.0.0"
---

# Crawl / Render Audit

## When to use

Invoked by `audit-orchestrator` as part of the full pipeline. Can also be run
standalone to check specifically whether a site is reachable, allowed to be
crawled, and whether its content survives being fetched without JavaScript
execution.

## Inputs

A `SiteSnapshot` — either passed in-process (orchestrator path) or loaded
from a `snapshot.json` file / produced by a standalone bounded crawl
(`--url`, see script `--help`).

## Outputs

A JSON list of `Finding` objects (see `audit_engine/models.py`). Each is
already evidence-backed and severity-scored; nothing downstream needs to
reinterpret them.

## Procedure

```bash
python scripts/analyze.py --url example.com          # standalone, bounded crawl
python scripts/analyze.py --snapshot snapshot.json    # shared-snapshot path
```

Checks performed (see `references/checklist.md` for exact thresholds):
robots.txt blocking, sitemap absence, broken internal links, missing
canonical tags, and JS-dependency (via a static heuristic score, escalated to
a real Playwright render-delta check only for a handful of suspicious pages
when Playwright is installed — see the module docstring in
`audit_engine/parsing/render_heuristics.py`).

## Constraints

- Never flags "this site uses JavaScript" on its own — only a confirmed
  render-delta or multiple independent static signals plus very low raw word
  count triggers `js_dependent_content` (avoids penalizing modern sites that
  happen to use a JS framework but still server-render their content).
- If zero pages were fetched at all (DNS/connectivity failure), emits exactly
  one `site_unreachable` finding and nothing else — no other check in this
  module runs on an empty page set.
- Read-only: only ever issues GET/HEAD requests, respects `robots.txt`.
