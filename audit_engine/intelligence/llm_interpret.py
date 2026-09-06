"""Optional LLM interpretation layer.

Everything upstream of this module is deterministic. The one place an LLM
call is allowed is here, for exactly one bounded task: turning a finding's
already-computed evidence into a sharper recommendation summary/rationale —
synthesis and prose, not fact-finding (spec section 6/32).

Contract (spec section 33 — never trust raw LLM output):
  1. The model is asked for strict JSON matching a 2-field schema.
  2. The response is validated against that schema.
  3. On invalid JSON: one repair attempt (extract the first {...} block, retry).
  4. On repeated failure, network error, missing dependency, or missing
     API key: fall back to the deterministic recommendation untouched.
     A malformed or unavailable LLM never breaks the pipeline or downgrades
     report validity — the deterministic text is already a complete,
     schema-valid suggested_action on its own.

Cost/latency control: called for at most `max_llm_calls` findings (highest
severity first), never once per page and never once per analyzer.
"""
from __future__ import annotations

import json
import os
import re

_SYSTEM_PROMPT = (
    "You are a technical writer for a website AI-discoverability audit tool. "
    "You receive one already-detected, evidence-backed finding and must sharpen its "
    "recommendation. Do not invent new facts, numbers, or evidence beyond what is given. "
    "Respond with ONLY a JSON object: "
    '{"summary": "<one specific, technically actionable sentence>", '
    '"rationale": "<one sentence on why this matters for AI discoverability/engagement>"}'
)

_REQUIRED_KEYS = {"summary", "rationale"}


def refine_recommendation(
    *, title: str, category: str, evidence_texts: list[str],
    deterministic_summary: str, deterministic_rationale: str, cfg,
) -> tuple[str, str, bool]:
    """Returns (summary, rationale, used_llm)."""
    if not cfg.get("analysis", "llm_enabled", True):
        return deterministic_summary, deterministic_rationale, False

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return deterministic_summary, deterministic_rationale, False

    try:
        import anthropic  # type: ignore
    except ImportError:
        return deterministic_summary, deterministic_rationale, False

    payload = {
        "finding_title": title,
        "category": category,
        "evidence": evidence_texts[:5],
        "deterministic_summary": deterministic_summary,
    }
    model = cfg.get("analysis", "llm_model", "claude-sonnet-5")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=250,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        raw_text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    except Exception:
        return deterministic_summary, deterministic_rationale, False

    data = _parse_and_validate(raw_text)
    if data is None:
        return deterministic_summary, deterministic_rationale, False
    return data["summary"], data["rationale"], True


def _parse_and_validate(raw_text: str) -> dict | None:
    data = _try_json(raw_text)
    if data is None:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            data = _try_json(match.group(0))
    if not isinstance(data, dict):
        return None
    if not _REQUIRED_KEYS.issubset(data.keys()):
        return None
    if not all(isinstance(data[k], str) and data[k].strip() for k in _REQUIRED_KEYS):
        return None
    if len(data["summary"]) > 600 or len(data["rationale"]) > 600:
        return None  # reject runaway output rather than truncate silently
    return data


def _try_json(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
