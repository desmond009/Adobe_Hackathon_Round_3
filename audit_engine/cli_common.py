"""Shared plumbing for the thin per-skill CLI scripts under skills/*/scripts/.

Keeps every analyze.py wrapper to ~20 lines: argument parsing, snapshot
resolution (load a shared snapshot.json, or crawl standalone for independent
testing of one skill), and JSON output are all defined once here instead of
copy-pasted six times.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from audit_engine.config import Config
from audit_engine.crawler.crawl import crawl_site
from audit_engine.crawler.url_utils import ensure_scheme, normalize_url
from audit_engine.models import Finding, SiteSnapshot
from audit_engine.snapshot_io import load_snapshot, save_snapshot


def build_cli_parser(skill_name: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=skill_name,
        description=f"Standalone runner for the {skill_name} skill. Normally the shared SiteSnapshot "
                    "is produced once by audit-orchestrator and passed to every specialized skill; "
                    "--url here is provided so this skill can also be run and tested in isolation.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Site/domain to crawl standalone (bounded crawl, for isolated testing).")
    group.add_argument("--snapshot", help="Path to a snapshot.json produced by a prior crawl stage.")
    parser.add_argument("--save-snapshot", help="If crawling standalone, also write the SiteSnapshot to this path.")
    parser.add_argument("--config", default=None, help="Path to an alternate config YAML (default: config/default.yaml).")
    return parser


def resolve_snapshot(args: argparse.Namespace, cfg: Config) -> SiteSnapshot:
    if args.snapshot:
        return load_snapshot(args.snapshot)
    snapshot = crawl_site(normalize_url(ensure_scheme(args.url)), cfg)
    if args.save_snapshot:
        save_snapshot(snapshot, args.save_snapshot)
    return snapshot


def findings_to_json(findings: list[Finding]) -> list[dict]:
    out = []
    for f in findings:
        d = asdict(f)
        out.append(d)
    return out


def print_json(obj) -> None:
    json.dump(obj, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
