"""Security helpers: redirects, CSV/HTML sanitization."""

from __future__ import annotations

from services.artifacts import build_meta_pack
from services.export import runs_to_csv
from services.security import csv_cell, html_attr, safe_next_url


def test_safe_next_url_blocks_open_redirects():
    assert safe_next_url("//evil.test") == "/"
    assert safe_next_url("https://evil.test/phish") == "/"
    assert safe_next_url("/\\evil") == "/"
    assert safe_next_url("dashboard") == "/"
    assert safe_next_url("/dashboard") == "/dashboard"
    assert safe_next_url("/dashboard?job=1") == "/dashboard?job=1"
    assert safe_next_url(None, fallback="/home") == "/home"


def test_csv_cell_neutralizes_formulas():
    assert csv_cell("=CMD()") == "'=CMD()"
    assert csv_cell("+1") == "'+1"
    assert csv_cell("ok") == "ok"


def test_html_attr_escapes():
    assert "&quot;" in html_attr('"x"')
    assert "&lt;" in html_attr("<script>")


def test_meta_pack_escapes_title():
    html = build_meta_pack(
        "https://example.com",
        {
            "domain": "example.com",
            "title": 'Brand"><script>alert(1)</script>',
            "description": "desc",
            "canonical": "https://example.com/",
            "lang": "it",
        },
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html or "&#x27;" in html or "&quot;" in html


def test_runs_to_csv_sanitizes_title():
    class R:
        id = 1
        site_id = 2
        domain = "example.com"
        url = "https://example.com"
        aio_score = 10
        geo_score = 20
        rating = {"code": "CCC", "score": 30}
        source = "manual"
        findings = []
        created_at = None
        page_title = "=HYPERLINK(\"http://evil\")"

    raw = runs_to_csv([R()]).decode("utf-8-sig")
    assert "'=HYPERLINK" in raw
