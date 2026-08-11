"""Fase 0 P0: brand Centropic + waitlist Plus vocabulary."""

from __future__ import annotations

from app import app


def test_interesse_plus_is_canonical():
    with app.test_client() as client:
        resp = client.get("/interesse-plus")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "/interesse-plus" in body
        assert "Plus" in body
        assert "Business" in body


def test_interesse_pro_redirects_to_plus():
    with app.test_client() as client:
        resp = client.get("/interesse-pro", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers["Location"].endswith("/interesse-plus")


def test_sitemap_lists_interesse_plus_not_pro():
    with app.test_client() as client:
        resp = client.get("/sitemap.xml")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "/interesse-plus" in body
        assert "/interesse-pro" not in body


def test_pricing_waitlist_links_interesse_plus_when_paddle_off(monkeypatch):
    monkeypatch.delenv("PADDLE_API_KEY", raising=False)
    monkeypatch.delenv("PADDLE_CLIENT_TOKEN", raising=False)
    monkeypatch.delenv("PADDLE_PRICE_PLUS_MONTHLY", raising=False)
    monkeypatch.delenv("PADDLE_PRICE_BUSINESS_MONTHLY", raising=False)
    with app.test_client() as client:
        resp = client.get("/prezzi")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert 'href="/interesse-plus"' in body or "/interesse-plus" in body
