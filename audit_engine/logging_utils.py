"""Structured, stage-tagged logging.

Every log line is prefixed with the stage that emitted it (spec section 34's
example log format), written to stderr so stdout stays reserved for the final
JSON report when the orchestrator is invoked as a CLI. Never logs response
bodies, headers, or secrets — only counts and short factual summaries.
"""
from __future__ import annotations

import sys


def log(stage: str, message: str) -> None:
    print(f"[{stage}] {message}", file=sys.stderr, flush=True)
