"""URL normalization and same-site scoping.

Kept dependency-free and deterministic: no PSL download, no network calls.
Same-domain matching uses a small embedded list of common multi-part public
suffixes (co.uk, com.au, ...) as a heuristic — good enough for "is this the
same site" without the complexity/non-determinism of fetching the full public
suffix list. This is a documented, intentional approximation (see README
Limitations).
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode

_SCHEME_RE = re.compile(r"^https?://", re.I)


def ensure_scheme(candidate: str) -> str:
    """Prepend https:// to a bare domain ("example.com" -> "https://example.com").
    Shared by every entry point that accepts a raw domain/URL string (the
    orchestrator's request validation and every standalone --url skill script)
    so "which scheme did we assume" is answered in exactly one place."""
    candidate = candidate.strip()
    return candidate if _SCHEME_RE.match(candidate) else f"https://{candidate}"

# Second-level suffixes where the *effective* registrable domain needs 3 labels
# instead of 2 (example.co.uk, not co.uk). Not exhaustive by design.
_MULTI_PART_SUFFIXES = {
    "co.uk", "org.uk", "gov.uk", "ac.uk", "co.in", "com.au", "net.au", "org.au",
    "co.jp", "co.nz", "co.za", "com.br", "com.mx", "com.sg",
}


def normalize_url(url: str, base: str | None = None, tracking_params: list[str] | None = None) -> str:
    """Resolve relative URLs, lowercase scheme/host, strip fragment and tracking params,
    remove default ports, and sort remaining query params for stable deduplication."""
    if base:
        url = urljoin(base, url)
    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    tracking = set(tracking_params or [])
    kept_params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in tracking]
    kept_params.sort()
    query = urlencode(kept_params)

    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"

    return urlunparse((scheme, netloc, path, "", query, ""))


def registrable_domain(hostname: str) -> str:
    """Best-effort registrable domain (see module docstring for the heuristic's limits)."""
    labels = hostname.lower().split(".")
    if len(labels) <= 2:
        return hostname.lower()
    last_two = ".".join(labels[-2:])
    if last_two in _MULTI_PART_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return last_two


def is_same_site(url: str, seed_hostname: str) -> bool:
    # Strip any port from *both* sides defensively: callers have historically passed a
    # raw netloc (host:port) here, and comparing a bare port-stripped host against one
    # that still carries ":port" silently fails every same-site check on non-default
    # ports (e.g. a local test server) — a bug real HTTPS/HTTP-on-80 sites never surface.
    host = urlparse(url).netloc.split(":")[0].lower()
    seed_host = seed_hostname.split(":")[0].lower()
    return registrable_domain(host) == registrable_domain(seed_host)


def url_depth_hint(url: str, seed_url: str) -> int:
    """Cheap structural depth estimate from path segment count, used for crawl prioritization
    before the real BFS depth is known."""
    path = urlparse(url).path.strip("/")
    return 0 if not path else len(path.split("/"))
