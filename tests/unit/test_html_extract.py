from audit_engine.parsing.html_extract import parse_page


def test_extracts_title_meta_headings_and_word_count():
    html = """
    <html lang="en"><head><title>Widgets | Acme</title>
    <meta name="description" content="We sell widgets.">
    <link rel="canonical" href="/widgets"></head>
    <body><h1>Widgets</h1><h2>Details</h2><p>A short paragraph about widgets and pricing.</p></body></html>
    """
    parsed = parse_page(html, "https://example.com/widgets")
    assert parsed["title"] == "Widgets | Acme"
    assert parsed["meta"]["description"] == "We sell widgets."
    assert parsed["canonical"] == "https://example.com/widgets"
    assert parsed["headings"] == [(1, "Widgets"), (2, "Details")]
    assert parsed["word_count"] > 0
    assert parsed["lang"] == "en"


def test_hidden_text_excluded_from_visible_text():
    html = '<body><p>Visible text here.</p><p style="display:none">Hidden text here.</p></body>'
    parsed = parse_page(html, "https://example.com/")
    assert "Visible text" in parsed["text"]
    assert "Hidden text" not in parsed["text"]


def test_internal_vs_external_link_classification():
    html = """
    <body>
      <a href="/about">About</a>
      <a href="https://example.com/contact">Contact</a>
      <a href="https://other.org/page">Other</a>
      <a href="mailto:hi@example.com">Email</a>
    </body>
    """
    parsed = parse_page(html, "https://example.com/")
    assert "https://example.com/about" in parsed["links_internal"]
    assert "https://example.com/contact" in parsed["links_internal"]
    assert "https://other.org/page" in parsed["links_external"]
    assert not any("mailto" in link for link in parsed["links_internal"] + parsed["links_external"])


def test_contact_signal_extraction():
    html = "<body><p>Reach us at support@example.com or (303) 555-0142.</p></body>"
    parsed = parse_page(html, "https://example.com/contact")
    assert "support@example.com" in parsed["contact_signals"]["emails"]
    assert parsed["contact_signals"]["phones"]


def test_page_role_inference():
    assert parse_page("<body></body>", "https://example.com/about")["page_role"] == "about"
    assert parse_page("<body></body>", "https://example.com/")["page_role"] == "home"
    assert parse_page("<body></body>", "https://example.com/random-page")["page_role"] == "other"
