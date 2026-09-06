"""Entity identity: could an AI system confuse this brand with another one?

Owns brand-name-consistency analysis exclusively (freshness-corroboration
deliberately does not duplicate this — see that module's docstring) so there
is exactly one place that reasons about "how many names does this site call
itself" and one Finding category for it.
"""
from __future__ import annotations

from audit_engine.models import Evidence, SiteSnapshot
from audit_engine.parsing.entity_extraction import extract_name_candidates, group_variants
from audit_engine.severity import FindingCandidate


def analyze(snapshot: SiteSnapshot, cfg) -> list[FindingCandidate]:
    ok_pages = snapshot.ok_pages()
    if not ok_pages:
        return []

    candidates: list[FindingCandidate] = []
    candidates += _check_inconsistent_name(ok_pages)
    candidates += _check_missing_about(ok_pages)
    candidates += _check_sameas_linking(ok_pages)
    return candidates


def _check_inconsistent_name(ok_pages: list) -> list[FindingCandidate]:
    candidates_named = extract_name_candidates(ok_pages)
    groups = group_variants(candidates_named)
    if len(groups) < 2 or len(candidates_named) < 3:
        return []  # too little signal to distinguish "typo" from "real inconsistency"

    total = sum(len(v) for v in groups.values())
    sorted_groups = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    minority = sum(len(v) for _, v in sorted_groups[1:])
    if minority < 2 or minority / total < 0.15:
        return []

    dominant_name = sorted_groups[0][1][0].name
    evidence = [
        Evidence(
            source_url=v.source_url, signal="org_name_variant",
            observed_value=f"Organization name rendered as {v.name!r} (source: {v.source_signal})",
            expected_value=f"Consistent with the dominant form {dominant_name!r}",
            confidence=0.75,
        )
        for _, variants in sorted_groups[1:3] for v in variants[:2]
    ]
    return [FindingCandidate(
        check_id="inconsistent_brand_name",
        evidence=evidence,
        scope=minority / total, confidence=0.75,
        recommendation_summary=f"Standardize on one canonical brand name (observed dominant form: "
                                f"{dominant_name!r}) across page titles, meta tags, structured data, and "
                                "footer text, so AI systems don't treat name variants as different entities.",
    )]


def _check_missing_about(ok_pages: list) -> list[FindingCandidate]:
    has_about = any(p.page_role == "about" for p in ok_pages)
    if has_about:
        return []
    return [FindingCandidate(
        check_id="missing_about_identity",
        evidence=[Evidence(
            source_url=ok_pages[0].url, signal="about_page_absent",
            observed_value=f"No page with an about/company-identity URL pattern found among "
                            f"{len(ok_pages)} crawled pages",
            confidence=0.55,
        )],
        scope=1.0, confidence=0.55,
        recommendation_summary="Publish a dedicated About/Company page stating who the organization is, "
                                "what it does, and where it operates — the single highest-leverage page "
                                "for AI entity resolution.",
    )]


def _check_sameas_linking(ok_pages: list) -> list[FindingCandidate]:
    home = next((p for p in ok_pages if p.page_role == "home"), ok_pages[0])
    org_blocks = [b for b in home.structured_data if "organization" in {t.lower() for t in b.get("types", [])}]
    if not org_blocks:
        return []  # covered by structured-data-audit's missing_organization_schema; avoid double-flagging
    has_sameas = any(b["properties"].get("sameAs") for b in org_blocks)
    if has_sameas:
        return []
    return [FindingCandidate(
        check_id="weak_entity_sameas_linking",
        evidence=[Evidence(
            source_url=home.url, signal="sameas_absent",
            observed_value="Organization structured data has no sameAs property linking to external "
                            "authoritative profiles",
            confidence=0.6,
        )],
        scope=1.0, confidence=0.6,
        recommendation_summary="Add sameAs links (official social profiles, Wikidata/Crunchbase entry, "
                                "business registry) to the Organization structured data to help AI systems "
                                "disambiguate this entity from similarly-named ones.",
        proactive=True,
    )]
