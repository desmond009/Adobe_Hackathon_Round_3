#!/usr/bin/env python3
"""CLI entrypoint for the recommendation-engine skill.

Takes the per-skill finding JSON files produced by the six specialized
analyze.py scripts (list[Finding-as-dict] each) and turns them into the
final validated audit report: deduplicate -> recommend (optional LLM
refinement) -> prioritize -> summarize -> validate against report/schema.json.

This is the manual-orchestration path — an agent that ran each specialized
skill as a separate tool call uses this to assemble the final report. The
single-shot path (skills/audit-orchestrator/scripts/run_audit.py) does the
same four steps in-process without touching disk.

Usage:
    python assemble_report.py --site example.com \\
        --findings cr.json sd.json ce.json fr.json ei.json en.json \\
        [--config path/to/config.yaml]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from audit_engine.config import load_config
from audit_engine.intelligence.dedup import deduplicate
from audit_engine.intelligence.prioritize import prioritize
from audit_engine.intelligence.recommend import refine_recommendations
from audit_engine.models import CrawlStats, Evidence, Finding, Recommendation
from audit_engine.report.builder import build_audit_result
from audit_engine.report.validator import validate_report


def _load_findings(paths: list[str]) -> list[Finding]:
    findings = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            raw_list = json.load(fh)
        for raw in raw_list:
            evidence = [Evidence(**e) for e in raw["evidence"]]
            action = Recommendation(**raw["suggested_action"])
            findings.append(Finding(**{**raw, "evidence": evidence, "suggested_action": action}))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--findings", nargs="+", required=True, help="JSON files from each specialized skill's analyze.py")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    findings = _load_findings(args.findings)

    findings = deduplicate(findings)
    findings = refine_recommendations(findings, cfg)
    findings = prioritize(findings)

    max_findings = cfg.get("report", "max_findings", 30)
    limitations = [
        "External corroboration was not performed: only on-site facts were observed and cross-checked.",
    ]
    result = build_audit_result(
        site=args.site, findings=findings,
        crawl_stats=CrawlStats(stopped_reason="assembled_from_precomputed_findings"),
        limitations=limitations, max_findings=max_findings,
    )
    report = result.to_report_dict()

    errors = validate_report(report)
    if errors:
        print(f"Final report failed schema validation: {errors}", file=sys.stderr)
        sys.exit(1)

    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
