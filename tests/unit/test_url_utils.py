from audit_engine.crawler.url_utils import is_same_site, normalize_url, registrable_domain


def test_normalize_strips_fragment_and_default_port():
    assert normalize_url("https://Example.com:443/Path/?b=2&a=1#frag") == "https://example.com/Path?a=1&b=2"


def test_normalize_strips_tracking_params():
    url = normalize_url("https://example.com/?utm_source=x&id=42", tracking_params=["utm_source"])
    assert url == "https://example.com/?id=42"


def test_normalize_resolves_relative_against_base():
    assert normalize_url("/about", base="https://example.com/blog/post") == "https://example.com/about"


def test_normalize_collapses_trailing_slash_but_keeps_root():
    assert normalize_url("https://example.com/about/") == "https://example.com/about"
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_registrable_domain_simple():
    assert registrable_domain("www.example.com") == "example.com"


def test_registrable_domain_multi_part_suffix():
    assert registrable_domain("shop.example.co.uk") == "example.co.uk"


def test_is_same_site_matches_subdomains():
    assert is_same_site("https://shop.example.com/x", "example.com")
    assert not is_same_site("https://example.org/x", "example.com")
