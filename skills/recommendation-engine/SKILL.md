---
name: recommendation-engine
description: Assembles the final audit report from the six specialized skills' findings - deduplicates by root cause while preserving distinct actionable problems, optionally refines the highest-severity recommendations via a schema-validated LLM call, computes deterministic priority ranking, and validates the result against the mandated report schema. Use as the last stage of the audit-orchestrator pipeline (invoked automatically), or standalone when assembling a report from independently-run specialized skills.
allowed-tools: ["Bash", "Read"]
metadata:
  category: synthesis
  version: "1.0.0"
---

# Recommendation Engine

## When to use

The final synthesis stage. When `audit-orchestrator` runs the single-shot
pipeline, this logic runs in-process (`audit_engine/intelligence/*` and
`audit_engine/report/*`) and this skill's own script is not invoked
separately. Use `scripts/assemble_report.py` directly only when you drove
the six specialized skills as separate tool calls and now need to combine
their outputs into one validated report.

## Inputs

Six JSON files, each a `list[Finding]` produced by one specialized skill's
`analyze.py --snapshot ... > out.json`.

## Outputs

The final report JSON matching `audit_engine/report/schema.json`.

## Procedure

```bash
python scripts/assemble_report.py --site example.com \
    --findings cr.json sd.json ce.json fr.json ei.json en.json
```

Steps (see `references/recommendation-catalog.md` for the severity and
priority formulas):

1. **Deduplicate** — collapse exact-duplicate candidates; tag (never merge)
   findings from *different* categories whose affected URLs substantially
   overlap with a shared `related_group` id.
2. **Recommend** — for the highest-severity findings only (bounded, default
   8), optionally ask an LLM to sharpen the recommendation's wording from
   the same evidence already attached — never to add new facts. Falls back
   silently to the deterministic recommendation if no API key, the
   `anthropic` package isn't installed, or the response fails schema
   validation.
3. **Prioritize** — deterministic `impact x confidence x implementation_leverage`
   ranking, assigning `priority_rank`.
4. **Validate** — the assembled report must pass `report/schema.json` or the
   run fails loudly rather than returning something malformed.

## Constraints

- Never invents a finding — this stage only reorganizes, prioritizes, and
  rephrases findings the six specialized skills already produced with
  evidence attached.
- The LLM call (if used) is schema-validated JSON only; invalid output is
  discarded in favor of the deterministic recommendation, never patched or
  guessed at.
- A report that fails schema validation is a bug to fix upstream, not
  something this stage should ever try to silently coerce into looking valid.
