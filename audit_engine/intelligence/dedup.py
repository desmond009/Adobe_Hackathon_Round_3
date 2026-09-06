"""Finding deduplication and root-cause grouping.

Two distinct operations, per spec section 17 — these are NOT the same thing:

  1. Exact-duplicate collapse: two candidates for the *same check_id* covering
     the *same affected URLs* are merged into one Finding (evidence unioned).
     This guards against an analyzer accidentally emitting the same signal
     twice; it should rarely fire in practice since each analyzer check
     function returns at most one candidate per run.

  2. Root-cause grouping (NOT merging): findings from *different categories*
     whose affected-URL sets substantially overlap (Jaccard similarity >= 0.5)
     likely reflect the same underlying problem observed through different
     lenses (e.g. "product page hard to extract" + "product schema missing" +
     "product page buried in navigation"). The spec is explicit that these
     remain distinct, actionable findings — grouping only tags them with a
     shared `related_group` id so a reader can see the connection, rather
     than collapsing three real problems into one under-specified finding.
"""
from __future__ import annotations

from collections import defaultdict

from audit_engine.models import Finding

_JACCARD_THRESHOLD = 0.5


def deduplicate(findings: list[Finding]) -> list[Finding]:
    findings = _collapse_exact_duplicates(findings)
    _tag_related_groups(findings)
    return findings


def _collapse_exact_duplicates(findings: list[Finding]) -> list[Finding]:
    by_key: dict[tuple[str, tuple[str, ...]], Finding] = {}
    ordered_keys: list[tuple[str, tuple[str, ...]]] = []
    for f in findings:
        key = (f.check_id, tuple(sorted(f.affected_urls)))
        if key in by_key:
            existing = by_key[key]
            existing_ids = {e.signal + e.source_url for e in existing.evidence}
            for e in f.evidence:
                if e.signal + e.source_url not in existing_ids:
                    existing.evidence.append(e)
        else:
            by_key[key] = f
            ordered_keys.append(key)
    return [by_key[k] for k in ordered_keys]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _tag_related_groups(findings: list[Finding]) -> None:
    parent = {f.id: f.id for f in findings}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i, f1 in enumerate(findings):
        urls1 = set(f1.affected_urls)
        for f2 in findings[i + 1:]:
            if f1.category == f2.category:
                continue  # relatedness grouping is specifically a *cross*-category signal
            if _jaccard(urls1, set(f2.affected_urls)) >= _JACCARD_THRESHOLD:
                union(f1.id, f2.id)

    groups: dict[str, list[str]] = defaultdict(list)
    for f in findings:
        groups[find(f.id)].append(f.id)

    group_label = {}
    counter = 1
    for root, members in groups.items():
        if len(members) < 2:
            continue
        group_label[root] = f"RG-{counter:02d}"
        counter += 1

    for f in findings:
        root = find(f.id)
        if root in group_label:
            f.related_group = group_label[root]
