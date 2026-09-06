#!/usr/bin/env python3
"""CLI entrypoint for the crawl-render-audit skill.

Usage:
    python analyze.py --url example.com [--save-snapshot snapshot.json]
    python analyze.py --snapshot snapshot.json
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from audit_engine.analyzers import crawl_render as analyzer
from audit_engine.cli_common import build_cli_parser, findings_to_json, print_json, resolve_snapshot
from audit_engine.config import load_config
from audit_engine.severity import build_finding


def main() -> None:
    args = build_cli_parser("crawl-render-audit").parse_args()
    cfg = load_config(args.config)
    snapshot = resolve_snapshot(args, cfg)
    threshold = cfg.get("analysis", "confidence_threshold", 0.55)

    findings = []
    for i, candidate in enumerate(analyzer.analyze(snapshot, cfg), start=1):
        finding = build_finding(candidate, f"CR-{i:03d}", threshold)
        if finding:
            findings.append(finding)
    print_json(findings_to_json(findings))


if __name__ == "__main__":
    main()
