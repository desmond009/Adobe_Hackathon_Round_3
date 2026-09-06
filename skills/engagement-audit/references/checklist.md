# Engagement checks

| check_id | Fires when |
|---|---|
| `missing_value_proposition_orientation` | Homepage H1s + meta description combined are <5 words |
| `no_clear_next_action` | >=40% of key pages (home/product/pricing) have no recognizable CTA phrase |
| `dead_end_page` | >=4 pages crawled; >=15% have zero outgoing internal links and >30 words of content |
| `thin_internal_linking` | >=5 pages crawled; >=40% of product/pricing pages are linked from <=1 other crawled page |

## Orientation vs. next-action vs. linking

These map to spec section 14's three engagement dimensions:

- **Orientation** — `missing_value_proposition_orientation` (does the
  homepage say what the business does, immediately).
- **Next action** — `no_clear_next_action` (is there an unambiguous path
  forward on key pages).
- **Context retention / friction** — `dead_end_page` and
  `thin_internal_linking` (can a visitor keep exploring, and are important
  pages reachable from more than one place).
