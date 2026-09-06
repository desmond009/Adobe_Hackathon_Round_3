"""Specialized analyzers.

Each analyzer is a pure function: `analyze(snapshot, cfg) -> list[FindingCandidate]`.
None of them crawl or fetch anything themselves — they consume the shared
SiteSnapshot the orchestrator built once. This keeps analyzers independently
unit-testable against a fixture SiteSnapshot and keeps runtime bounded (no
analyzer can accidentally trigger a second crawl).
"""
