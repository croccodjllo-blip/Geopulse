"""Public surfaces required for Paddle seller checks."""

from __future__ import annotations

import os

from app import app


def test_legal_and_contact_pages_are_public():
    client = app.test_client()
    for path in (
        "/privacy",
        "/termini",
        "/terms",
        "/rimborsi",
        "/refund",
        "/refund-policy",
        "/contatti",
        "/contact",
    ):
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code in {200, 301, 302}, path
        if resp.status_code in {301, 302}:
            # Canonical aliases may redirect; follow must land on 200.
            followed = client.get(path, follow_redirects=True)
            assert followed.status_code == 200, path


def test_homepage_exposes_contact_and_legal_links():
    client = app.test_client()
    html = client.get("/").get_data(as_text=True)
    assert "mailto:info@centropic.ai" in html
    assert "/contatti" in html or "/contact" in html
    assert "/privacy" in html
    assert "/termini" in html or "/terms" in html
    assert "/rimborsi" in html or "/refund" in html


def test_pricing_hides_yearly_without_catalog_price(monkeypatch):
    monkeypatch.delenv("PADDLE_PRICE_PLUS_YEARLY", raising=False)
    # Ensure monthly paddle path can still render.
    monkeypatch.setenv("PAYMENTS_PROVIDER", "paddle")
    monkeypatch.setenv("PADDLE_API_KEY", "test")
    monkeypatch.setenv("PADDLE_PRICE_PLUS_MONTHLY", "pri_test_monthly")
    client = app.test_client()
    html = client.get("/prezzi").get_data(as_text=True)
    assert "19,99" in html or "19.99" in html
    assert "14,99" not in html and "14.99" not in html
    assert "191.90" not in html
    assert "191,90" not in html
    assert "143.90" not in html
    assert "143,90" not in html


def test_legacy_stripe_webhooks_gone():
    client = app.test_client()
    for path in ("/billing/webhook", "/billing/topup-webhook"):
        resp = client.post(path, data=b"{}", content_type="application/json")
        assert resp.status_code == 410, path
