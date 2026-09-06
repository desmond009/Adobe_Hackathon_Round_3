"""Final report schema validation.

The orchestrator calls this on every report before returning it. A report
that fails validation is a bug in the pipeline, not a possible LLM slip — by
this point everything has already passed through typed dataclasses, so a
validation failure here should be loud, not silently swallowed.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.json"


def load_schema() -> dict:
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_report(report: dict) -> list[str]:
    """Returns a list of human-readable validation errors; empty list = valid."""
    schema = load_schema()
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(report), key=lambda e: list(e.path))
    messages = [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]

    ids = [f.get("id") for f in report.get("findings", [])]
    if len(ids) != len(set(ids)):
        messages.append("findings contain duplicate ids")

    summary = report.get("summary", {})
    counted = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in report.get("findings", []):
        sev = f.get("severity")
        if sev in counted:
            counted[sev] += 1
    for sev in ("critical", "high", "medium", "low"):
        if summary.get(sev, 0) != counted[sev]:
            messages.append(f"summary.{sev} ({summary.get(sev, 0)}) does not match findings count ({counted[sev]})")
    if summary.get("total_findings") != len(report.get("findings", [])):
        messages.append("summary.total_findings does not match len(findings)")

    return messages
