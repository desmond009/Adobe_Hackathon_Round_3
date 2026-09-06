# Pipeline stages

```
AuditRequest
  -> validate + normalize (URL, domain)
  -> crawl_site()                     one shared SiteSnapshot
       -> robots.txt
       -> sitemap discovery
       -> priority-ordered bounded crawl (fetch + parse + structured-data + JS heuristic per page)
  -> six analyzers, each: analyze(snapshot, cfg) -> list[FindingCandidate]
       crawl-render-audit, structured-data-audit, content-extractability-audit,
       freshness-corroboration-audit, entity-identity-audit, engagement-audit
  -> severity.build_finding() per candidate      (false-positive gate + severity scoring)
  -> intelligence.dedup.deduplicate()            (exact-duplicate collapse + related-group tagging)
  -> intelligence.recommend.refine_recommendations()  (optional, bounded LLM polish)
  -> intelligence.prioritize.prioritize()        (priority_rank assignment)
  -> report.builder.build_audit_result()         (summary counts, limitations)
  -> report.validator.validate_report()          (schema.json — must pass or the run fails loudly)
  -> final JSON report
```

## Why one shared snapshot

Every analyzer receives the *same* `SiteSnapshot` object (or the same
`snapshot.json` file, in the manual-orchestration path). None of them
crawl independently. This means:

- the site is fetched once per page, not once per analyzer (6x fewer requests),
- every analyzer's evidence refers to the exact same crawl (no risk of the
  page changing between two analyzers' looks at it), and
- the crawl's own limits (`max_pages`, `overall_budget_s`, ...) bound the
  *entire* audit's cost, not just one stage of it.

## Why deterministic-first

Every fact an analyzer needs (HTTP status, JSON-LD presence, heading levels,
word counts, link graphs, contact-info regexes, date parsing) is computed in
`audit_engine/parsing/` and `audit_engine/crawler/` with plain code, not an
LLM call. The one optional LLM call (`intelligence/llm_interpret.py`) only
*rephrases* an already-computed, evidence-backed recommendation — it cannot
invent a finding, and its output is JSON-schema-validated with a deterministic
fallback if it's unavailable, disabled, or returns something unusable.

## Why false positives are hard to produce

1. Every `FindingCandidate` requires non-empty `evidence` (`severity.build_finding`
   rejects candidates with none).
2. Every candidate carries an analyzer-computed `confidence`; candidates below
   `config.analysis.confidence_threshold` (default 0.55) are dropped outright.
3. Checks that depend on a *sample* (broken links, canonical coverage, heading
   hierarchy) require a minimum sample size before they fire at all, and always
   report the sample size in evidence text ("12/12 product pages", never "the
   website").
4. `crawl_render.analyze()` short-circuits to a single "site unreachable"
   finding when zero pages were fetched, instead of letting every other check
   fire misleading noise on top of a connectivity failure.
