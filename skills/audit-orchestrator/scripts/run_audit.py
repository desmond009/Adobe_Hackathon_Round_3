#!/usr/bin/env python3
"""CLI entrypoint for the audit-orchestrator skill (the marketplace entrypoint).

Runs the full pipeline in one process: validate -> crawl -> six specialized
analyzers -> dedupe -> recommend -> prioritize -> validated final report.
Prints the final JSON report to stdout; all progress logging goes to stderr
so stdout is always clean, parseable JSON.

Usage:
    python run_audit.py example.com
    python run_audit.py https://example.com --config custom.yaml
    python run_audit.py example.com --out report.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from audit_engine.config import load_config
from audit_engine.orchestrator import InvalidAuditRequestError, run_audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", help="Domain or URL to audit, e.g. example.com or https://example.com")
    parser.add_argument("--config", default=None, help="Path to an alternate config YAML")
    parser.add_argument("--out", default=None, help="Write the report to this file instead of stdout")
    args = parser.parse_args()

    cfg = load_config(args.config)

    try:
        report = run_audit(args.site, cfg)
    except InvalidAuditRequestError as exc:
        print(f"Invalid input: {exc}", file=sys.stderr)
        sys.exit(2)

    output = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Report written to {args.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
