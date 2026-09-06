from bs4 import BeautifulSoup

from audit_engine.parsing.render_heuristics import compute_js_dependency_score

_SPA_SHELL = """
<html><head><script src="/a.js"></script><script src="/b.js"></script><script src="/c.js"></script></head>
<body><div id="root"></div><noscript>Please enable JavaScript to use this app which does many things
that are described here in enough words to exceed the raw body word count by a wide margin indeed.</noscript>
</body></html>
"""

_NORMAL_PAGE = """
<html><head><script src="/analytics.js"></script></head>
<body><h1>About Acme</h1><p>Acme is a company that makes widgets for people who need widgets in their
daily lives, and this paragraph has plenty of real, substantive, server-rendered text content in it.</p>
</body></html>
"""


def test_spa_shell_scores_high():
    soup = BeautifulSoup(_SPA_SHELL, "lxml")
    text_len = len(soup.get_text(strip=True).split())
    score = compute_js_dependency_score(_SPA_SHELL, soup, word_count=0)
    assert score >= 0.5


def test_normal_server_rendered_page_scores_low():
    soup = BeautifulSoup(_NORMAL_PAGE, "lxml")
    word_count = len(soup.get_text(separator=" ", strip=True).split())
    score = compute_js_dependency_score(_NORMAL_PAGE, soup, word_count=word_count)
    assert score < 0.5


def test_score_is_bounded_0_to_1():
    soup = BeautifulSoup(_SPA_SHELL, "lxml")
    score = compute_js_dependency_score(_SPA_SHELL, soup, word_count=0)
    assert 0.0 <= score <= 1.0
