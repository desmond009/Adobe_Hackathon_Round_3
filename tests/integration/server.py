"""Local static-file HTTP server for integration tests.

Serves a copy of a fixture directory (never the original — tests must not
mutate checked-in fixtures) on an ephemeral localhost port, substituting the
BASE_URL_PLACEHOLDER token in .html/.xml/.txt files with the server's actual
URL once the port is known. This lets fixtures declare absolute URLs (as
real sitemaps/canonicals/JSON-LD do) without hardcoding a port.
"""
from __future__ import annotations

import http.server
import shutil
import socketserver
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

_TEXT_SUFFIXES = {".html", ".xml", ".txt"}


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: A002 - stdlib signature
        pass  # keep test output clean; failures still surface via assertions


@contextmanager
def serve_fixture(fixture_dir: Path):
    tmp_dir = tempfile.mkdtemp(prefix="brand_audit_fixture_")
    try:
        shutil.copytree(fixture_dir, tmp_dir, dirs_exist_ok=True)

        def handler_factory(*args, **kwargs):
            return _QuietHandler(*args, directory=tmp_dir, **kwargs)

        httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler_factory)
        port = httpd.server_address[1]
        base_url = f"http://127.0.0.1:{port}"

        for path in Path(tmp_dir).rglob("*"):
            if path.is_file() and path.suffix in _TEXT_SUFFIXES:
                text = path.read_text(encoding="utf-8")
                if "BASE_URL_PLACEHOLDER" in text:
                    path.write_text(text.replace("BASE_URL_PLACEHOLDER", base_url), encoding="utf-8")

        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield base_url
        finally:
            httpd.shutdown()
            httpd.server_close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
