# How to Run & Test — Quick Guide

A focused, copy-paste guide for actually running the audit and running the
test suite. For architecture, scoring model, and design rationale, see
[`README.md`](README.md).

## 1. One-time setup

```bash
cd /Users/vijender/Documents/Adobe_Project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Every new terminal session, just re-activate:

```bash
source .venv/bin/activate
```

## 2. Run it against a real website

```bash
python skills/audit-orchestrator/scripts/run_audit.py example.com
```

Accepts a bare domain or a full URL:

```bash
python skills/audit-orchestrator/scripts/run_audit.py https://example.com
```

Save the report to a file instead of printing it (progress logs go to
stderr, so stdout is always clean JSON):

```bash
python skills/audit-orchestrator/scripts/run_audit.py example.com --out report.json
```

**Try it on a few different sites** to see how the findings change:

```bash
python skills/audit-orchestrator/scripts/run_audit.py stripe.com
python skills/audit-orchestrator/scripts/run_audit.py python.org
python skills/audit-orchestrator/scripts/run_audit.py <any domain you like>
```

### Read the report quickly from the terminal

```bash
python -c "
import json
r = json.load(open('report.json'))
print('site:', r['site'])
print('summary:', r['summary'])
for f in r['findings']:
    print('-', f['severity'], f['category'], '|', f['title'])
"
```

## 3. Tune the crawl (optional)

Every value in `config/default.yaml` can be overridden via env vars
(`BRAND_AUDIT__<SECTION>__<KEY>`) without editing any file:

```bash
BRAND_AUDIT__CRAWL__MAX_PAGES=5 BRAND_AUDIT__CRAWL__OVERALL_BUDGET_S=30 \
    python skills/audit-orchestrator/scripts/run_audit.py example.com
```

## 4. Run one specialized skill standalone

Each of the six analyzer skills works on its own, not just inside the full
pipeline:

```bash
python skills/structured-data-audit/scripts/analyze.py --url example.com
python skills/content-extractability-audit/scripts/analyze.py --url example.com
```

## 5. Run the automated test suite

```bash
pip install -r requirements-dev.txt
pytest -v
```

41 tests, fully offline (spins up local HTTP servers over fixture sites —
no real network calls), runs in a couple of seconds:

- Unit tests: URL normalization, structured-data extraction, severity
  scoring, dedup semantics, HTML extraction, render heuristics, schema
  validation.
- Integration tests: three fixture sites under `tests/fixtures/sites/`
  (`good_ecommerce`, `spa_js_only`, `poorly_structured`) plus an
  unreachable-domain case.

Run just one file or one test if you're iterating:

```bash
pytest tests/unit/test_severity.py -v
pytest -k "poorly_structured" -v
```

## 6. Validate compliance / schema

```bash
python scripts/validate_marketplace.py         # marketplace.json + all 8 SKILL.md files
python scripts/validate_report.py report.json  # any report against the mandated JSON schema
```

## 7. Optional extras

```bash
# LLM recommendation polish (rephrases up to the top 8 findings only —
# never invents a finding; pipeline is fully functional without this):
export ANTHROPIC_API_KEY=sk-...
python skills/audit-orchestrator/scripts/run_audit.py example.com

# Real render-delta checks via headless Chromium (static heuristic alone
# is used if this isn't installed):
pip install playwright && playwright install chromium
```

## 8. Troubleshooting

| Symptom | Likely cause |
|---|---|
| Only 1 page crawled | Site has no sitemap and few/no internal links reachable from the seed URL — expected, not a bug. Check the `[CRAWLER]` log line on stderr. |
| `robots.txt not found` in logs | Site has none; crawl proceeds (nothing to disallow). |
| Report differs when you re-run the same site | Sites change; the crawl is also bounded (`max_pages=25` by default) and priority-ordered, so which 25 pages get sampled can shift slightly run to run. |
| `ModuleNotFoundError: audit_engine` | You ran a script from outside the project root, or the venv isn't active — `cd` into the project root and `source .venv/bin/activate` first. |
| Findings missing structured-data/entity checks | That analyzer had 0 candidates to evaluate on this site — see the `[STRUCTURED-DATA-AUDIT] N candidate(s) evaluated` line on stderr. |
