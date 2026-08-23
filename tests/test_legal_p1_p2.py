"""Legal P1/P2: cookie/AI/trust/a11y pages, consent UI, policy versioning."""

from __future__ import annotations

from pathlib import Path

from services.legal_docs import POLICY_VERSIONS, cookie_inventory, legal_nav_links


def test_policy_versions_cover_p1_p2_docs():
    for key in (
        "privacy",
        "terms",
        "cookies",
        "ai",
        "trust",
        "accessibility",
        "dpa",
    ):
        assert key in POLICY_VERSIONS
        assert POLICY_VERSIONS[key]


def test_cookie_inventory_categories():
    rows = cookie_inventory(analytics_active=True, ads_active=True)
    cats = {r.category for r in rows}
    assert "necessary" in cats
    assert "analytics" in cats
    assert "advertising" in cats
    assert any(r.name.startswith("centropic_consent") for r in rows)


def test_legal_nav_endpoints_exist():
    from app import app

    for link in legal_nav_links():
        assert link["endpoint"] in app.view_functions, link["endpoint"]


def test_public_legal_p1_p2_routes():
    from app import app

    client = app.test_client()
    paths = [
        "/cookie",
        "/cookies",
        "/ai",
        "/ai-transparency",
        "/trust",
        "/security",
        "/accessibilita",
        "/accessibility",
        "/privacy",
        "/termini",
    ]
    for path in paths:
        r = client.get(path, follow_redirects=True)
        assert r.status_code == 200, path
        html = r.get_data(as_text=True)
        assert "centropic" in html.lower() or "Centropic" in html


def test_privacy_and_terms_have_saas_clauses():
    privacy = Path("templates/privacy.html").read_text(encoding="utf-8")
    assert "Periodi di conservazione" in privacy or "conservazione" in privacy
    assert "CCPA" in privacy or "UK GDPR" in privacy
    assert "cookies_policy" in privacy
    assert "ai_transparency" in privacy
    assert "trust_security" in privacy
    terms = Path("templates/termini.html").read_text(encoding="utf-8")
    assert "così com’è" in terms or "come disponibile" in terms
    assert "Limitazione di responsabilità" in terms
    assert "garantisce" not in terms.lower() or "non garantisce" in terms.lower()
    # Avoid absolute product warranty language
    assert "Il Servizio è fornito" in terms or "così com" in terms


def test_cookie_banner_has_granular_controls():
    base = Path("templates/base.html").read_text(encoding="utf-8")
    assert "cookie-consent-accept" in base
    assert "cookie-consent-reject" in base
    assert "cookie-consent-customize" in base
    assert "cookie-consent-analytics" in base
    assert "cookie-consent-ads" in base
    assert 'data-cookie-manage' in base
    assert "cookies_policy" in base
    js = Path("static/js/analytics.js").read_text(encoding="utf-8")
    assert "data-cookie-manage" in js
    assert "centropicOpenCookiePrefs" in js
    assert "cookie-consent-save" in js


def test_settings_has_billing_cancel_path():
    settings = Path("templates/settings.html").read_text(encoding="utf-8")
    assert 'id="billing"' in settings
    assert "billing_portal" in settings
    assert "annullare" in settings.lower() or "cancellazione" in settings.lower()


def test_sitemap_includes_new_legal_urls():
    from app import app

    client = app.test_client()
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    for path in ("/cookie", "/ai", "/trust", "/accessibilita"):
        assert path in body


def test_footer_and_templates_reference_new_pages():
    base = Path("templates/base.html").read_text(encoding="utf-8")
    assert "ai_transparency" in base
    assert "trust_security" in base
    assert "accessibility_statement" in base
    for name in (
        "templates/cookies.html",
        "templates/ai_transparency.html",
        "templates/trust.html",
        "templates/accessibility.html",
    ):
        text = Path(name).read_text(encoding="utf-8")
        assert "policy_version" in text
