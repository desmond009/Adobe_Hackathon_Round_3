#!/usr/bin/env python3
"""Standalone CLI: validate a previously generated audit report JSON file
against audit_engine/report/schema.json (spec section 29, "Audit output").

Usage:
    python scripts/validate_report.py path/to/report.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit_engine.report.validator import validate_report


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/validate_report.py path/to/report.json", file=sys.stderr)
        sys.exit(2)

    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    errors = validate_report(report)
    if errors:
        print(f"INVALID: {len(errors)} issue(s)")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("OK: report is schema-valid.")


if __name__ == "__main__":
    main()
