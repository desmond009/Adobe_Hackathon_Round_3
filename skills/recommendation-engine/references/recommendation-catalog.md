# Severity and priority formulas

## Severity (per finding, `audit_engine/severity.py`)

```
composite = 0.35*impact + 0.25*scope + 0.20*confidence + 0.20*business_importance
```

- `impact`, `business_importance`: static, per-check values from
  `audit_engine/catalog.py` (how much this class of problem generally
  degrades AI discoverability/engagement, and how central the affected
  pages/facts typically are — never tuned to a specific website).
- `scope`, `confidence`: computed at runtime by the analyzer from the actual
  evidence (e.g. `scope = affected_pages / sampled_pages`).

A weighted sum, not a product, so one narrow-but-severe issue found with
high confidence on a highly important page can't be washed out by a merely
moderate scope. Thresholds: `>=0.75` critical, `>=0.55` high, `>=0.35`
medium, else low.

## False-positive gate

A `FindingCandidate` becomes a `Finding` only if:
1. it has at least one `Evidence` entry, and
2. its `confidence >= config.analysis.confidence_threshold` (default 0.55).

Both checks happen in exactly one place (`severity.build_finding`) so every
analyzer gets the same gate for free.

## Priority ranking (`audit_engine/intelligence/prioritize.py`)

```
priority_score = check.impact * finding.confidence * implementation_leverage(category)
```

`implementation_leverage` is a per-category constant (structured-data and
crawlability fixes are typically cheap markup/config changes — leverage
0.85/0.75; content and engagement fixes typically need copy or IA rework —
leverage 0.6/0.55). Findings are ordered by `(severity, priority_score)`
descending and get a `priority_rank`. This is a *ranking* signal only — the
severity label itself never depends on it.

## Deduplication vs. grouping

See `audit_engine/intelligence/dedup.py`. Two different operations:
exact-duplicate **collapse** (same check_id + same affected URLs -> merge
evidence into one finding), and cross-category **grouping** (overlapping
affected URLs across different categories -> tag with a shared
`related_group`, never merge — spec section 17 is explicit that these stay
distinct, actionable findings).
