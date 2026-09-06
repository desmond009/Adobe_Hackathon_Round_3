---
name: engagement-audit
description: Audits on-site engagement mechanics - whether the homepage orients a first-time visitor within the first content block, whether key pages offer a clear next action (CTA), internal-linking health, and dead-end pages with no outgoing links. Evidence-based, not a subjective "does this look nice" judgment. Use as part of the audit-orchestrator pipeline, or standalone to check a site's navigational and orientation health.
allowed-tools: ["Bash", "Read"]
metadata:
  category: engagement
  version: "1.0.0"
---

# Engagement Audit

## When to use

Invoked by `audit-orchestrator`. Standalone use: checking whether a visitor
(human or agentic browser) landing on the site can tell where they are, what
the business does, and what to do next, purely from the link graph and text
structure already extracted for every page.

## Inputs / Outputs

Same contract as every specialized skill: consumes a `SiteSnapshot`, emits a
JSON list of `Finding` objects.

## Procedure

```bash
python scripts/analyze.py --url example.com
python scripts/analyze.py --snapshot snapshot.json
```

See `references/checklist.md` for exact thresholds.

## Constraints

- Every check here is link-graph or text-pattern based on data the crawler
  already extracted — no additional requests, no subjective visual judgment
  ("this looks bad") ever appears in a finding.
- CTA detection uses a curated phrase list (spec section 14's "next action"
  examples: sign up, get started, book, contact us, request a demo, buy now,
  add to cart, learn more, subscribe, start a trial, schedule, talk to
  sales, download) — a page is only flagged when *none* of these appear.
- `thin_internal_linking` and `dead_end_page` both require a minimum crawled
  page count (5 and 4 respectively) before they can fire — on a tiny site
  there isn't enough of a link graph to say anything meaningful about it.
