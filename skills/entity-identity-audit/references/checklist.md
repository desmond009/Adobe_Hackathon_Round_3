# Entity identity checks

| check_id | Fires when |
|---|---|
| `inconsistent_brand_name` | >=3 name candidates extracted; grouping by normalized form yields >=2 groups where the minority group(s) represent >=15% of mentions (and >=2 occurrences) |
| `missing_about_identity` | No crawled page has an about/company-role URL (`about`, `company`, `our-story`, `who-we-are`) |
| `weak_entity_sameas_linking` (proactive) | An Organization block exists on the homepage but has no `sameAs` property |

## Name candidate sources (see `audit_engine/parsing/entity_extraction.py`)

1. `<title>` — the segment after a ` | `, ` - `, ` – `, ` — `, or ` : ` separator
2. `og:site_name` meta tag
3. JSON-LD `Organization`/`WebSite` block `name` property
4. Footer copyright text (`© YYYY Name`, `(c) Name`, `copyright Name`)

## Normalization for grouping

`normalize_name()` lowercases, strips punctuation, and removes standalone
legal-suffix tokens (`inc`, `llc`, `ltd`, `corp`, `corporation`, `co`) as
whole words only — "NexaCorp" (fused, one token) and "Nexa Corp Inc" (three
tokens) normalize to *different* groups ("nexacorp" vs "nexa"), which is
exactly the kind of real-world inconsistency this check exists to catch.
