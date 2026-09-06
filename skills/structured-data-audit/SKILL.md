---
name: structured-data-audit
description: Audits schema.org structured data (JSON-LD, Microdata, RDFa) for coverage, correctness, and consistency with visible page content - Organization/WebSite on the homepage, Product/Offer on product pages, LocalBusiness where a physical location is implied, malformed JSON-LD, and price/fact mismatches between structured data and rendered text. Use as part of the audit-orchestrator pipeline, or standalone to check a site's structured-data quality for AI answer engines.
allowed-tools: ["Bash", "Read"]
metadata:
  category: structured_data
  version: "1.0.0"
---

# Structured Data Audit

## When to use

Invoked by `audit-orchestrator`. Standalone use: checking whether a site's
schema.org markup is present, complete, valid, and trustworthy enough for an
AI answer engine to cite directly instead of re-parsing visible text.

## Inputs / Outputs

Same contract as every specialized skill: consumes a `SiteSnapshot`, emits a
JSON list of `Finding` objects.

## Procedure

```bash
python scripts/analyze.py --url example.com
python scripts/analyze.py --snapshot snapshot.json
```

See `references/schema-coverage.md` for the exact schema.org types checked
and what "incomplete" / "malformed" / "mismatched" mean concretely.

## Constraints

- Never reports generic "no structured data" — every finding names a specific
  schema.org type against a specific, quantified page population (e.g.
  "0/12 product pages contain Product/Offer JSON-LD").
- Distinguishes **absent** (no block found) from **malformed** (a block was
  attempted but fails to parse) from **incomplete** (parses, but is missing
  expected properties) from **visible-mismatch** (parses fine, but disagrees
  with the page's own visible text) — these are different findings with
  different remediation, not one collapsed "structured data problem".
- The homepage-price/visible-price mismatch check only fires when *both* a
  structured price and a visible price are present and they disagree — never
  on absence of either.
- Includes two **proactive** checks (`missing_faq_schema_opportunity`,
  `missing_breadcrumb_schema`) that suggest markup for content that's already
  present but unmarked — these are opportunities, not defects, and are
  labeled `"proactive": true` in the final report.
