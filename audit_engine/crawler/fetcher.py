"""Bounded, polite HTTP fetching.

Single responsibility: turn a URL into a `FetchResult` while respecting
timeouts, response-size caps, redirect limits, and content-type filtering.
Never raises on network failure — a broken page must never crash the audit
(spec section 7/26); failures come back as a `FetchResult` with `ok=False`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import requests


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int | None
    ok: bool
    error: str | None
    content_type: str | None
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""
    truncated: bool = False
    redirect_count: int = 0


def build_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
    })
    return session


def fetch(
    session: requests.Session,
    url: str,
    *,
    timeout_s: int,
    max_response_size_bytes: int,
    max_redirects: int,
    allowed_content_types: list[str],
    method: str = "GET",
) -> FetchResult:
    try:
        resp = session.request(
            method, url, timeout=timeout_s, stream=True, allow_redirects=True,
        )
    except requests.exceptions.TooManyRedirects as exc:
        return FetchResult(url=url, final_url=url, status=None, ok=False,
                            error=f"too_many_redirects: {exc}", content_type=None)
    except requests.exceptions.SSLError as exc:
        return FetchResult(url=url, final_url=url, status=None, ok=False,
                            error=f"ssl_error: {exc}", content_type=None)
    except requests.exceptions.Timeout:
        return FetchResult(url=url, final_url=url, status=None, ok=False,
                            error="timeout", content_type=None)
    except requests.exceptions.ConnectionError as exc:
        return FetchResult(url=url, final_url=url, status=None, ok=False,
                            error=f"connection_error: {exc}", content_type=None)
    except requests.RequestException as exc:
        return FetchResult(url=url, final_url=url, status=None, ok=False,
                            error=f"request_error: {exc}", content_type=None)

    redirect_count = len(resp.history)
    if redirect_count > max_redirects:
        resp.close()
        return FetchResult(url=url, final_url=resp.url, status=resp.status_code, ok=False,
                            error="max_redirects_exceeded", content_type=None,
                            redirect_count=redirect_count)

    content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    status_ok = resp.status_code < 400

    if method == "HEAD":
        resp.close()
        return FetchResult(
            url=url, final_url=resp.url, status=resp.status_code, ok=status_ok, error=None,
            content_type=content_type, headers=dict(resp.headers), redirect_count=redirect_count,
        )

    if content_type and allowed_content_types and content_type not in allowed_content_types:
        resp.close()
        return FetchResult(
            url=url, final_url=resp.url, status=resp.status_code, ok=status_ok,
            error=None if status_ok else f"http_{resp.status_code}",
            content_type=content_type, headers=dict(resp.headers), redirect_count=redirect_count,
        )

    body = bytearray()
    truncated = False
    try:
        for chunk in resp.iter_content(chunk_size=8192):
            body.extend(chunk)
            if len(body) > max_response_size_bytes:
                truncated = True
                break
    except requests.exceptions.RequestException as exc:
        resp.close()
        return FetchResult(url=url, final_url=resp.url, status=resp.status_code, ok=False,
                            error=f"stream_error: {exc}", content_type=content_type,
                            redirect_count=redirect_count)
    finally:
        resp.close()

    encoding = resp.encoding or "utf-8"
    try:
        text = body.decode(encoding, errors="replace")
    except (LookupError, TypeError):
        text = body.decode("utf-8", errors="replace")

    return FetchResult(
        url=url,
        final_url=resp.url,
        status=resp.status_code,
        ok=status_ok,
        error=None if status_ok else f"http_{resp.status_code}",
        content_type=content_type,
        headers=dict(resp.headers),
        text=text,
        truncated=truncated,
        redirect_count=redirect_count,
    )
