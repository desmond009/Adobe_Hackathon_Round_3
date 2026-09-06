"""robots.txt handling.

Wraps the stdlib RobotFileParser (battle-tested, spec-compliant enough for our
purposes) and adds Sitemap: directive extraction, which RobotFileParser does
not expose cleanly across versions.

Fails open in one specific, safe direction: if robots.txt cannot be fetched
at all (404, timeout, DNS failure), we treat the site as allowed — this
matches standard crawler behavior (absence of robots.txt means no
restriction) rather than treating a network hiccup as a block.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.robotparser import RobotFileParser

import requests


@dataclass
class RobotsInfo:
    found: bool
    allowed_root: bool
    disallow_rules: list[str] = field(default_factory=list)
    sitemap_urls: list[str] = field(default_factory=list)
    fetch_error: str | None = None

    def is_allowed(self, url: str, user_agent: str) -> bool:
        if not self.found:
            return True
        return self._parser.can_fetch(user_agent, url)  # type: ignore[attr-defined]


def fetch_robots(root_url: str, user_agent: str, timeout_s: int) -> RobotsInfo:
    robots_url = root_url.rstrip("/") + "/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=timeout_s, headers={"User-Agent": user_agent})
    except requests.RequestException as exc:
        return RobotsInfo(found=False, allowed_root=True, fetch_error=str(exc))

    if resp.status_code >= 400:
        return RobotsInfo(found=False, allowed_root=True)

    parser = RobotFileParser()
    parser.set_url(robots_url)
    lines = resp.text.splitlines()
    parser.parse(lines)

    sitemap_urls = [
        line.split(":", 1)[1].strip()
        for line in lines
        if line.lower().startswith("sitemap:")
    ]
    disallow_rules = [
        line.split(":", 1)[1].strip()
        for line in lines
        if line.lower().startswith("disallow:") and line.split(":", 1)[1].strip()
    ]

    info = RobotsInfo(
        found=True,
        allowed_root=parser.can_fetch(user_agent, root_url),
        disallow_rules=disallow_rules,
        sitemap_urls=sitemap_urls,
    )
    info._parser = parser  # type: ignore[attr-defined]
    return info
