---
name: content-extractability-audit
description: Audits whether a machine can reliably extract concrete facts from a site's machine-readable text - who the company is, what it offers, who it's for, where it operates, plus vague marketing language, weak heading hierarchy, ambiguous pricing, and missing contact information. Independent of structured data - this checks the actual visible/extractable text. Use as part of the audit-orchestrator pipeline, or standalone to check whether an AI agent could answer basic factual questions about a business from its site alone.
allowed-tools: ["Bash", "Read"]
metadata:
  category: content_extractability
  version: "1.0.0"
---

# Content Extractability Audit

## When to use

Invoked by `audit-orchestrator`. Standalone use: answering "could an AI agent
extract who this company is, what it sells, who it's for, and where it
operates, from this site's text alone?"

## Inputs / Outputs

Same contract as every specialized skill: consumes a `SiteSnapshot`, emits a
JSON list of `Finding` objects.

## Procedure

```bash
python scripts/analyze.py --url example.com
python scripts/analyze.py --snapshot snapshot.json
```

See `references/checklist.md` for exactly what each of the four "who / what
/ who-for / where" checks looks for and why they're deliberately
presence-based, not quality-graded, to keep the false-positive rate low.

## Constraints

- This is explicitly **not** an SEO audit (spec section 11) — it never scores
  keyword density, meta-tag length, or ranking factors. It only asks whether
  a specific, answerable fact is present in extractable text.
- The "who/what/who-for/where" checks are intentionally coarse (presence of
  *any* qualifying signal, not a judgment of how good that signal is) — this
  keeps the check deterministic and low-false-positive. Judging *quality* of
  an already-present answer is exactly the kind of ambiguous, subjective task
  better suited to the optional LLM layer in `recommendation-engine`, not to
  a hard-coded rule here.
- `vague_value_proposition` uses a curated buzzword list and a density
  threshold (not a single-hit trigger) — one marketing phrase on an otherwise
  concrete page is not a finding.
