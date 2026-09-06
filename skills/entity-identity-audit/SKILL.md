---
name: entity-identity-audit
description: Audits whether a site establishes one clear, unambiguous organizational identity - consistent brand naming across titles/meta/structured-data/footer text, presence of an About/Company page, and sameAs links to authoritative external profiles. Flags what would make an AI system confuse this entity with a similarly-named one. Use as part of the audit-orchestrator pipeline, or standalone to check a brand's entity clarity.
allowed-tools: ["Bash", "Read"]
metadata:
  category: entity_identity
  version: "1.0.0"
---

# Entity Identity Audit

## When to use

Invoked by `audit-orchestrator`. Standalone use: checking whether an AI
system resolving "who is this organization" from the site alone would land
on one consistent answer.

## Inputs / Outputs

Same contract as every specialized skill: consumes a `SiteSnapshot`, emits a
JSON list of `Finding` objects.

## Procedure

```bash
python scripts/analyze.py --url example.com
python scripts/analyze.py --snapshot snapshot.json
```

See `references/checklist.md` for how name variants are extracted and
grouped, and the thresholds that separate a real inconsistency from a single
stray typo.

## Constraints

- Name-variant extraction is shared with `freshness-corroboration-audit` via
  `audit_engine/parsing/entity_extraction.py` — this skill owns the
  *finding* for brand-name inconsistency exclusively, so the two skills
  never both flag the same underlying signal as two different findings.
- `inconsistent_brand_name` requires >=3 total name candidates across the
  crawl and the minority variant(s) to represent >=15% of mentions (and
  >=2 occurrences) — a single odd title on one page is not enough evidence.
- `weak_entity_sameas_linking` only fires when an Organization block already
  exists but lacks `sameAs` — if Organization schema is missing entirely,
  that's `structured-data-audit`'s `missing_organization_schema` finding
  instead, to avoid double-flagging the same root cause.
