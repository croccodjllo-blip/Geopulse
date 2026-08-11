"""Google Search Console HTML verification file must be served at site root."""

from __future__ import annotations

from app import app


def test_google_site_verification_html_file():
    client = app.test_client()
    resp = client.get("/googlee1d69b8c33683acd.html")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True).strip()
    assert body == "google-site-verification: googlee1d69b8c33683acd.html"
