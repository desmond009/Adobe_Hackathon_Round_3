# Freshness / corroboration checks

| check_id | Fires when |
|---|---|
| `no_freshness_signal` | >=2 pricing/product/FAQ-role pages crawled and >=50% have no date signal at all |
| `stale_content_signal` | A page's date signal is >730 days old |
| `outdated_contact_info_pattern` | >=2 pages each publish a phone number, and those numbers disagree |

## Date sources checked, in order

1. Meta tags: `article:modified_time`, `article:published_time`, `og:updated_time`, `date`, `last-modified`
2. JSON-LD `dateModified` / `datePublished` on any structured-data block on the page
3. A visible "last updated" / "updated on" / "published on" / "as of" phrase followed by a parseable date

## Evidence tiers (spec section 13)

- **Observed on-site fact** — what every finding here reports.
- **Cross-page contradiction** — `outdated_contact_info_pattern`; a stronger
  signal because it doesn't require knowing which value is "correct", only
  that two on-site sources disagree.
- **Externally corroborated fact** — not implemented in this build. Fabricating
  this would be worse than omitting it (spec section 13), so `audit-orchestrator`
  states the limitation explicitly in every report instead.
