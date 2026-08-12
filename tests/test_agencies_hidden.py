"""Agencies marketing page is retired from public navigation."""

from __future__ import annotations

import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_agenzie_returns_404(client):
    assert client.get("/agenzie").status_code == 404


def test_nav_and_footer_omit_agencies_links(client):
    html = client.get("/").get_data(as_text=True)
    assert 'href="/agenzie"' not in html
    assert ">Agenzie<" not in html
    assert "Per agenzie" not in html


def test_sitemap_omits_agenzie(client):
    body = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/agenzie" not in body
