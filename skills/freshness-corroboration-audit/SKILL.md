---
name: freshness-corroboration-audit
description: Audits publication/modification date signals, staleness of time-sensitive pages, and cross-page consistency of facts like phone numbers. Distinguishes an observed on-site fact from an externally corroborated one - this build never fabricates external verification and states that limitation explicitly. Use as part of the audit-orchestrator pipeline, or standalone to check how current and internally consistent a site's information is.
allowed-tools: ["Bash", "Read"]
metadata:
  category: freshness_corroboration
  version: "1.0.0"
---

# Freshness / Corroboration Audit

## When to use

Invoked by `audit-orchestrator`. Standalone use: checking whether
time-sensitive pages (pricing, product, FAQ) carry date signals, whether any
are stale, and whether facts that should agree across pages (like a phone
number) actually do.

## Inputs / Outputs

Same contract as every specialized skill: consumes a `SiteSnapshot`, emits a
JSON list of `Finding` objects.

## Procedure

```bash
python scripts/analyze.py --url example.com
python scripts/analyze.py --snapshot snapshot.json
```

See `references/checklist.md` for date sources checked and staleness
thresholds.

## Constraints

- **No external corroboration is performed.** This skill only compares
  on-site facts against each other. `audit-orchestrator` always adds a
  `limitations` entry stating this plainly — never claim a fact was
  "verified" when only "observed on one or more pages" is true.
- Date extraction only trusts standard signals (`article:modified_time`,
  `article:published_time`, JSON-LD `dateModified`/`datePublished`, or a
  visible "last updated"/"as of" string) — dates are never inferred or
  guessed from surrounding prose.
- The staleness threshold (730 days) is a generic, documented default, not
  tuned to any specific site or industry (spec section 38: generalization).
- The cross-page contact-consistency check requires >=2 pages to each
  publish a phone number *and* those numbers to disagree — a single page
  with a number, or full agreement, produces no finding.
- Brand-name consistency is owned entirely by `entity-identity-audit`, not
  duplicated here, to keep the two skills' responsibilities non-overlapping.
