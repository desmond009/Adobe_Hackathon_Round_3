from bs4 import BeautifulSoup

from audit_engine.parsing.structured_data import extract_structured_data


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def test_extracts_valid_json_ld_organization():
    html = """
    <html><head><script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "Organization", "name": "Acme", "url": "https://acme.com"}
    </script></head><body></body></html>
    """
    blocks, malformed = extract_structured_data(_soup(html))
    assert not malformed
    assert len(blocks) == 1
    assert blocks[0]["format"] == "json-ld"
    assert blocks[0]["types"] == ["Organization"]
    assert blocks[0]["properties"]["name"] == "Acme"


def test_flattens_at_graph_array():
    html = """
    <script type="application/ld+json">
    {"@graph": [
      {"@type": "Organization", "name": "Acme"},
      {"@type": "WebSite", "name": "Acme Site"}
    ]}
    </script>
    """
    blocks, malformed = extract_structured_data(_soup(html))
    assert not malformed
    assert {b["types"][0] for b in blocks} == {"Organization", "WebSite"}


def test_malformed_json_ld_is_reported_not_silently_dropped():
    # missing comma between properties: genuinely broken JSON, not repairable by our
    # conservative trailing-comma fixup, so it must surface as a malformed-data signal.
    html = '<script type="application/ld+json">{ "@type": "Organization" "name": "Acme" }</script>'
    blocks, malformed = extract_structured_data(_soup(html))
    assert blocks == []
    assert len(malformed) == 1


def test_trailing_comma_is_repaired():
    html = '<script type="application/ld+json">{"@type": "Organization", "name": "Acme",}</script>'
    blocks, malformed = extract_structured_data(_soup(html))
    assert not malformed
    assert blocks[0]["properties"]["name"] == "Acme"


def test_extracts_microdata_top_level_scope_only():
    html = """
    <div itemscope itemtype="https://schema.org/Product">
      <span itemprop="name">Widget</span>
      <div itemscope itemtype="https://schema.org/Brand">
        <span itemprop="name">Acme</span>
      </div>
    </div>
    """
    blocks, _ = extract_structured_data(_soup(html))
    product = next(b for b in blocks if b["types"] == ["Product"])
    assert product["properties"]["name"] == "Widget"
    brand = next(b for b in blocks if b["types"] == ["Brand"])
    assert brand["properties"]["name"] == "Acme"
