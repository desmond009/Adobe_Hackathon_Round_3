---
name: audit-orchestrator
description: Entrypoint for the Brand AI-Readiness Audit marketplace. Given a website domain or URL, runs a bounded read-only crawl, invokes the six specialized audit skills against one shared site snapshot, and returns a single evidence-backed JSON report scoring the site's discoverability and engagement for AI agents and answer engines. Use this skill whenever a user asks to "audit a site's AI readiness/discoverability", "check if my website is machine-readable", or "score how well an AI agent could understand this brand's website".
allowed-tools: ["Bash", "Read"]
metadata:
  category: orchestration
  version: "1.0.0"
---

# Audit Orchestrator

## When to use

The user gives you a domain or URL and wants a structured audit of how
discoverable, machine-readable, and engaging that site is for AI agents and
answer engines (not general SEO). This is the marketplace's only entrypoint —
every other skill here is invoked by this one, not directly by a user.

## Inputs

- `site` (string, required): a domain (`example.com`) or full URL (`https://example.com`).

## Outputs

One JSON object on stdout matching `audit_engine/report/schema.json`:
`site`, `audited_at`, `summary` (finding counts by severity), `findings[]`
(each with `id`, `title`, `severity`, `evidence`, `suggested_action`, plus
non-breaking enrichment fields — `category`, `confidence`, `evidence_detail`,
`related_group`), and `limitations` (what this audit could not verify).

## Procedure

Run the single-shot pipeline script — it performs every pipeline stage
(validate → crawl → six analyzers → dedupe → recommend → prioritize →
validate-and-return) in one process against one shared `SiteSnapshot`, which
is both faster and more consistent than re-invoking each specialized skill
as a separate tool call:

```bash
python skills/audit-orchestrator/scripts/run_audit.py <site>
```

Progress is logged to stderr, stage by stage (`[CRAWLER]`, `[STRUCTURED-DATA-AUDIT]`,
`[ORCHESTRATOR]`, `[REPORT]`, ...); stdout carries only the final JSON. Report
the JSON back to the user, optionally summarizing the top few findings in
prose — but do not alter the JSON's fields or values.

If you need to explain *why* a specific finding fired, read that finding's
category's skill under `skills/<category>-audit/SKILL.md` — each documents
exactly what its checks look for and why, in `references/checklist.md`.

### Manual, skill-by-skill orchestration (advanced)

If you are asked to demonstrate the marketplace's skill decomposition rather
than just get a report, you can drive the same pipeline as separate tool
calls, sharing one crawl across all of them:

```bash
python skills/crawl-render-audit/scripts/analyze.py --url <site> --save-snapshot /tmp/snapshot.json
python skills/structured-data-audit/scripts/analyze.py --snapshot /tmp/snapshot.json > /tmp/sd.json
python skills/content-extractability-audit/scripts/analyze.py --snapshot /tmp/snapshot.json > /tmp/ce.json
python skills/freshness-corroboration-audit/scripts/analyze.py --snapshot /tmp/snapshot.json > /tmp/fr.json
python skills/entity-identity-audit/scripts/analyze.py --snapshot /tmp/snapshot.json > /tmp/ei.json
python skills/engagement-audit/scripts/analyze.py --snapshot /tmp/snapshot.json > /tmp/en.json
python skills/crawl-render-audit/scripts/analyze.py --snapshot /tmp/snapshot.json > /tmp/cr.json
python skills/recommendation-engine/scripts/assemble_report.py --site <site> \
    --findings /tmp/cr.json /tmp/sd.json /tmp/ce.json /tmp/fr.json /tmp/ei.json /tmp/en.json
```

See `references/pipeline.md` for what each stage does and why it's ordered
this way.

## Constraints

- Read-only. Never submit forms, log in, or write to the target site.
- Respects `robots.txt` and same-domain scoping automatically (in the crawler,
  not something this skill needs to reason about).
- Bounded by `config/default.yaml` (`crawl.max_pages`, `crawl.overall_budget_s`,
  ...) so a run stays well under the 5-minute target even on large sites.
- Never hand-author the final report yourself. The Python pipeline is the
  only place severity/evidence/schema validation logic lives — if the script
  fails, report the error rather than fabricating a plausible-looking report.
