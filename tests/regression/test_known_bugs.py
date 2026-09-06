"""One test per bug found and fixed during development (spec section 28:
"every bug discovered during testing should become a regression test").
"""
from audit_engine.crawler.url_utils import ensure_scheme, is_same_site, normalize_url


def test_is_same_site_ignores_port_on_both_sides():
    """Found via the poorly_structured fixture integration test: comparing a
    port-stripped link host against a seed hostname that still carried ":port"
    made every same-site check fail, so the crawler silently never followed any
    internal link on a site reached via a non-default port (e.g. a local test
    server on 127.0.0.1:PORT). Real HTTPS/HTTP-on-80/443 sites never hit this
    because normalize_url() already drops those default ports — it only showed
    up once we started crawling fixtures over a real local HTTP server."""
    assert is_same_site("http://127.0.0.1:54321/about", "127.0.0.1:54321")
    assert is_same_site("http://127.0.0.1:54321/about", "127.0.0.1")
    assert not is_same_site("http://evil.example.com/about", "127.0.0.1:54321")


def test_ensure_scheme_lets_bare_domains_normalize_correctly():
    """Found via the manual (skill-by-skill) orchestration path: every standalone
    analyze.py's --url flag fed a bare domain like "example.com" straight into
    normalize_url(), which only defaults an *empty* scheme to https but does nothing
    about the missing "//", so it produced a malformed URL ("https:example.com") that
    then crashed crawl_site() when it tried to split out the host. The orchestrator's
    own build_audit_request() already handled this correctly; the fix was to share
    that scheme-defaulting logic via ensure_scheme() instead of only having it in one
    of the two entry points."""
    assert ensure_scheme("example.com") == "https://example.com"
    assert ensure_scheme("http://example.com") == "http://example.com"
    assert normalize_url(ensure_scheme("example.com")) == "https://example.com/"
