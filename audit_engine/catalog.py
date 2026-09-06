"""The check catalog: static metadata for every check the system can run.

This is the single place that says "how much does check X matter" (impact,
business_importance) and "what category/title does it belong to". Analyzers
supply the *dynamic* parts at runtime (scope, confidence, evidence). Keeping
this split means:

  * severity scoring is consistent across all six analyzers (no copy-pasted
    scoring logic that quietly drifts out of sync), and
  * adding a new check is a two-line catalog entry plus the analyzer code
    that detects it — not a new scoring scheme.

impact and business_importance are both 0..1 and reflect general principles
("missing Organization identity confuses every downstream AI answer") rather
than anything about a specific website, per the generalization requirement.
"""
from __future__ import annotations

from dataclasses import dataclass

from audit_engine.models import Category


@dataclass(frozen=True)
class CheckDefinition:
    id: str
    category: str
    title: str
    impact: float                # 0..1 — how much this degrades AI discoverability/engagement if true
    business_importance: float   # 0..1 — how central the affected pages/facts typically are
    proactive: bool = False      # True => this check only ever produces proactive suggestions


CATALOG: dict[str, CheckDefinition] = {}


def _register(defn: CheckDefinition) -> CheckDefinition:
    CATALOG[defn.id] = defn
    return defn


# --------------------------------------------------------------------------- #
# Crawlability / render (crawl-render-audit)
# --------------------------------------------------------------------------- #
_register(CheckDefinition("site_unreachable", Category.CRAWLABILITY,
    "Site could not be reached during the audit crawl", impact=0.9, business_importance=0.95))
_register(CheckDefinition("robots_blocks_crawl", Category.CRAWLABILITY,
    "robots.txt blocks crawling of important content", impact=0.95, business_importance=0.9))
_register(CheckDefinition("no_sitemap", Category.CRAWLABILITY,
    "No XML sitemap discovered", impact=0.4, business_importance=0.6))
_register(CheckDefinition("broken_internal_links", Category.CRAWLABILITY,
    "Broken internal links found", impact=0.5, business_importance=0.6))
_register(CheckDefinition("redirect_chain", Category.CRAWLABILITY,
    "Long redirect chains detected", impact=0.35, business_importance=0.5))
_register(CheckDefinition("missing_canonical", Category.CRAWLABILITY,
    "Pages missing canonical tags", impact=0.3, business_importance=0.5))
_register(CheckDefinition("duplicate_canonical_conflict", Category.CRAWLABILITY,
    "Canonical tag conflicts with page identity", impact=0.45, business_importance=0.55))
_register(CheckDefinition("js_dependent_content", Category.CRAWLABILITY,
    "Important content is materially harder to extract without JS execution", impact=0.75, business_importance=0.8))
_register(CheckDefinition("thin_server_rendered_content", Category.CRAWLABILITY,
    "Server-rendered HTML carries very little visible text", impact=0.6, business_importance=0.7))

# --------------------------------------------------------------------------- #
# Structured data (structured-data-audit)
# --------------------------------------------------------------------------- #
_register(CheckDefinition("missing_organization_schema", Category.STRUCTURED_DATA,
    "No Organization/WebSite structured data on the homepage", impact=0.85, business_importance=0.95))
_register(CheckDefinition("missing_product_schema", Category.STRUCTURED_DATA,
    "Product/Offer structured data missing on product pages", impact=0.75, business_importance=0.85))
_register(CheckDefinition("missing_localbusiness_schema", Category.STRUCTURED_DATA,
    "LocalBusiness structured data missing where a physical location is implied", impact=0.6, business_importance=0.7))
_register(CheckDefinition("malformed_structured_data", Category.STRUCTURED_DATA,
    "Structured data present but fails to parse as valid JSON-LD", impact=0.55, business_importance=0.6))
_register(CheckDefinition("incomplete_structured_data", Category.STRUCTURED_DATA,
    "Structured data present but missing required/expected properties", impact=0.45, business_importance=0.6))
_register(CheckDefinition("structured_data_visible_mismatch", Category.STRUCTURED_DATA,
    "Structured data contradicts the page's visible content", impact=0.7, business_importance=0.75))
_register(CheckDefinition("duplicate_structured_data_type", Category.STRUCTURED_DATA,
    "Multiple conflicting blocks of the same schema.org type on one page", impact=0.4, business_importance=0.5))
_register(CheckDefinition("missing_faq_schema_opportunity", Category.STRUCTURED_DATA,
    "FAQ-shaped content is not marked up as FAQPage", impact=0.3, business_importance=0.4, proactive=True))
_register(CheckDefinition("missing_breadcrumb_schema", Category.STRUCTURED_DATA,
    "No BreadcrumbList structured data despite clear site hierarchy", impact=0.25, business_importance=0.4, proactive=True))

# --------------------------------------------------------------------------- #
# Content extractability (content-extractability-audit)
# --------------------------------------------------------------------------- #
_register(CheckDefinition("unanswerable_who", Category.CONTENT_EXTRACTABILITY,
    "Machine-readable content cannot establish who the company is", impact=0.9, business_importance=0.9))
_register(CheckDefinition("unanswerable_what", Category.CONTENT_EXTRACTABILITY,
    "Machine-readable content cannot establish what is offered", impact=0.9, business_importance=0.9))
_register(CheckDefinition("unanswerable_who_for", Category.CONTENT_EXTRACTABILITY,
    "Machine-readable content does not identify a target audience", impact=0.55, business_importance=0.6))
_register(CheckDefinition("unanswerable_where", Category.CONTENT_EXTRACTABILITY,
    "Machine-readable content does not establish where the business operates", impact=0.5, business_importance=0.55))
_register(CheckDefinition("vague_value_proposition", Category.CONTENT_EXTRACTABILITY,
    "Key pages rely on vague marketing language instead of concrete facts", impact=0.5, business_importance=0.6))
_register(CheckDefinition("facts_locked_in_images", Category.CONTENT_EXTRACTABILITY,
    "Material facts appear to be conveyed only through images, not text", impact=0.65, business_importance=0.65))
_register(CheckDefinition("weak_heading_hierarchy", Category.CONTENT_EXTRACTABILITY,
    "Poor heading structure impairs machine parsing of page hierarchy", impact=0.35, business_importance=0.45))
_register(CheckDefinition("ambiguous_pricing", Category.CONTENT_EXTRACTABILITY,
    "Pricing is referenced but not stated in extractable text", impact=0.45, business_importance=0.55))
_register(CheckDefinition("missing_contact_context", Category.CONTENT_EXTRACTABILITY,
    "No machine-readable contact information found", impact=0.4, business_importance=0.5))

# --------------------------------------------------------------------------- #
# Freshness / corroboration (freshness-corroboration-audit)
# --------------------------------------------------------------------------- #
_register(CheckDefinition("no_freshness_signal", Category.FRESHNESS_CORROBORATION,
    "No publication/modification date signals found on time-sensitive pages", impact=0.4, business_importance=0.5))
_register(CheckDefinition("stale_content_signal", Category.FRESHNESS_CORROBORATION,
    "Content carries a modification date well past typical relevance windows", impact=0.5, business_importance=0.55))
_register(CheckDefinition("cross_page_fact_contradiction", Category.FRESHNESS_CORROBORATION,
    "The same fact is stated inconsistently across pages", impact=0.7, business_importance=0.75))
_register(CheckDefinition("outdated_contact_info_pattern", Category.FRESHNESS_CORROBORATION,
    "Contact information differs between pages that should agree", impact=0.55, business_importance=0.6))

# --------------------------------------------------------------------------- #
# Entity identity (entity-identity-audit)
# --------------------------------------------------------------------------- #
_register(CheckDefinition("inconsistent_brand_name", Category.ENTITY_IDENTITY,
    "The organization's name is rendered inconsistently across the site", impact=0.75, business_importance=0.85))
_register(CheckDefinition("missing_about_identity", Category.ENTITY_IDENTITY,
    "No About/Company page establishing organizational identity", impact=0.6, business_importance=0.7))
_register(CheckDefinition("weak_entity_sameas_linking", Category.ENTITY_IDENTITY,
    "No sameAs/external identity links (social, registries) to disambiguate the entity", impact=0.4, business_importance=0.5, proactive=True))
_register(CheckDefinition("conflicting_org_description", Category.ENTITY_IDENTITY,
    "The organization is described inconsistently across pages/metadata", impact=0.6, business_importance=0.65))

# --------------------------------------------------------------------------- #
# Engagement (engagement-audit)
# --------------------------------------------------------------------------- #
_register(CheckDefinition("missing_value_proposition_orientation", Category.ENGAGEMENT,
    "Homepage does not clearly state what the business does within the first content block", impact=0.7, business_importance=0.85))
_register(CheckDefinition("no_clear_next_action", Category.ENGAGEMENT,
    "Key pages provide no clear next action (CTA) for a visitor", impact=0.55, business_importance=0.7))
_register(CheckDefinition("navigation_context_loss", Category.ENGAGEMENT,
    "Navigation does not preserve context between related pages", impact=0.4, business_importance=0.55))
_register(CheckDefinition("thin_internal_linking", Category.ENGAGEMENT,
    "Important pages are weakly connected by internal links", impact=0.35, business_importance=0.5))
_register(CheckDefinition("dead_end_page", Category.ENGAGEMENT,
    "Pages found with no outgoing internal links (dead ends)", impact=0.45, business_importance=0.5))


# Implementation leverage: how cheap/fast the typical fix is relative to its impact
# (spec section 20's priority_score = impact x scope x confidence x implementation_leverage).
# Modeled per category rather than per check: markup/metadata fixes (structured data,
# crawlability) are consistently cheaper to ship than content or IA rework (engagement,
# content extractability), which is the real driver of the difference in practice.
CATEGORY_LEVERAGE: dict[str, float] = {
    Category.STRUCTURED_DATA: 0.85,
    Category.CRAWLABILITY: 0.75,
    Category.FRESHNESS_CORROBORATION: 0.7,
    Category.ENTITY_IDENTITY: 0.65,
    Category.CONTENT_EXTRACTABILITY: 0.6,
    Category.ENGAGEMENT: 0.55,
}


def implementation_leverage(category: str) -> float:
    return CATEGORY_LEVERAGE.get(category, 0.65)


def get(check_id: str) -> CheckDefinition:
    try:
        return CATALOG[check_id]
    except KeyError as exc:
        raise KeyError(f"Unknown check_id '{check_id}' — register it in audit_engine/catalog.py") from exc
