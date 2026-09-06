# Structured data checks

| check_id | Schema.org focus | Fires when |
|---|---|---|
| `missing_organization_schema` | Organization / WebSite | Homepage has no Organization/WebSite/Corporation/LocalBusiness JSON-LD, Microdata, or RDFa block |
| `incomplete_structured_data` | Organization | An Organization/WebSite block exists but is missing `name`, `url`, or `logo` |
| `missing_product_schema` | Product / Offer | >=2 product-role pages crawled; some fraction have no Product block (evidence states "N/M product pages") |
| `missing_localbusiness_schema` | LocalBusiness | Page text implies a physical location (address/hours/directions keywords, or a contact-role page) but no LocalBusiness/Store/Organization block exists anywhere |
| `malformed_structured_data` | any | A `<script type="application/ld+json">` block does not parse as JSON, even after a conservative trailing-comma repair attempt |
| `structured_data_visible_mismatch` | Product/Offer | A Product block's `offers.price` disagrees with a price found in the same page's visible text |
| `missing_faq_schema_opportunity` (proactive) | FAQPage | A page has >=3 headings ending in `?` and no FAQPage block exists anywhere on the site |
| `missing_breadcrumb_schema` (proactive) | BreadcrumbList | >=2 pages have a deep URL path (implying a category hierarchy) and no BreadcrumbList block exists anywhere |

## Extraction formats supported

- **JSON-LD**: `@graph` arrays and top-level arrays are both flattened to
  individual typed nodes. A block that fails `json.loads` gets one
  conservative repair attempt (strip trailing commas before `]`/`}`); still
  broken means a `malformed_structured_data` finding, not silent omission.
- **Microdata**: every `itemscope` (nested or not) becomes its own typed
  block; each `itemprop` is attributed to its *nearest* enclosing `itemscope`
  so nesting (e.g. `Product > Brand`, `Product > AggregateRating`) doesn't
  bleed properties across entities.
- **RDFa**: best-effort `typeof`/`property` pair extraction only. Complex
  RDFa (vocab prefixes, nested `resource` chains) is explicitly out of scope
  — see the module docstring in `audit_engine/parsing/structured_data.py`.
