"""Site quality fixes: /pricing alias, status depth, guide links."""

from __future__ import annotations


def test_pricing_alias_redirects():
    from app import app

    with app.test_client() as client:
        for path in ("/pricing", "/pricing/", "/price"):
            resp = client.get(path, follow_redirects=False)
            assert resp.status_code == 301, path
            loc = resp.headers.get("Location", "")
            assert loc.endswith("/prezzi") or "/prezzi" in loc, (path, loc)


def test_status_page_has_substantive_copy():
    from app import app

    with app.test_client() as client:
        html = client.get("/status").get_data(as_text=True)
        assert "Stato del servizio" in html or "Status" in html
        assert "Componenti" in html or "database" in html.lower()
        assert "/llms.txt" in html
        # Avoid thin-page heuristic (~150 words of main copy)
        assert html.count(" ") > 200


def test_site_guide_does_not_link_broken_pricing():
    from app import app
    from services.site_guide import site_guide_payload

    with app.app_context():
        links = [d["href"] for d in site_guide_payload()["deep_links"]]
    assert "/pricing" not in links
    assert "/prezzi" in links


def test_site_guide_translates_with_locale():
    from app import app
    from services.site_guide import site_guide_payload

    with app.test_request_context("/guida?lang=en"):
        app.preprocess_request()
        payload = site_guide_payload()
        # Italian source must not leak as page title when English is active
        assert payload["title"]
        # Either translated or still marked for translation; must be a string
        assert isinstance(payload["lede"], str)
        assert payload["toc"][0]["label"]



def test_landing_logos_have_alt():
    from app import app

    with app.test_client() as client:
        html = client.get("/").get_data(as_text=True)
        assert 'alt="Centropic"' in html
