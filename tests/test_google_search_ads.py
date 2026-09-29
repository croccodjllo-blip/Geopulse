"""Google Search + Ads: hreflang, sitemap, robots, conversions."""

from __future__ import annotations

import hashlib
from pathlib import Path

from services.seo import (
    ads_sha256_email,
    canonical_with_lang,
    hreflang_alternates,
    language_alternate_url,
    request_is_search_crawler,
    schema_in_language,
    sitemap_xhtml_links,
)

ROOT = Path(__file__).resolve().parents[1]


def test_hreflang_default_locale_is_clean_url():
    alts = hreflang_alternates("https://centropic.ai", "/prezzi")
    by_code = {row["code"]: row["href"] for row in alts}
    assert by_code["it"] == "https://centropic.ai/prezzi"
    assert by_code["en"] == "https://centropic.ai/prezzi?lang=en"
    assert by_code["zh-CN"] == "https://centropic.ai/prezzi?lang=zh"
    assert by_code["x-default"] == "https://centropic.ai/prezzi"
    assert "it" in by_code


def test_canonical_with_lang_only_for_non_default():
    assert (
        canonical_with_lang("https://centropic.ai", "/register", None)
        == "https://centropic.ai/register"
    )
    assert (
        canonical_with_lang("https://centropic.ai", "/register", "it")
        == "https://centropic.ai/register"
    )
    assert (
        canonical_with_lang("https://centropic.ai", "/register", "en")
        == "https://centropic.ai/register?lang=en"
    )


def test_home_alternate_keeps_trailing_slash():
    assert language_alternate_url("https://centropic.ai", "/", "it") == "https://centropic.ai/"
    assert (
        language_alternate_url("https://centropic.ai", "/", "en")
        == "https://centropic.ai/?lang=en"
    )


def test_schema_in_language_maps_og():
    assert schema_in_language("it") == "it-IT"
    assert schema_in_language("en") == "en-US"
    assert schema_in_language("zh") == "zh-CN"


def test_crawler_ua_detected():
    assert request_is_search_crawler("Mozilla/5.0 (compatible; Googlebot/2.1)")
    assert request_is_search_crawler("AdsBot-Google (+http://www.google.com/adsbot.html)")
    assert not request_is_search_crawler("Mozilla/5.0 Chrome/120.0")


def test_ads_sha256_email_normalizes():
    expected = hashlib.sha256(b"ada@example.com").hexdigest()
    assert ads_sha256_email("  Ada@Example.com ") == expected
    assert ads_sha256_email("") is None
    assert ads_sha256_email("not-an-email") is None


def test_sitemap_xhtml_escapes_and_lists_langs():
    xml = sitemap_xhtml_links("https://centropic.ai", "/prezzi")
    assert 'hreflang="en"' in xml
    assert 'href="https://centropic.ai/prezzi?lang=en"' in xml
    assert 'hreflang="x-default"' in xml


def test_robots_allows_lang_query_and_adsbot():
    from app import app

    body = app.test_client().get("/robots.txt").get_data(as_text=True)
    assert "Disallow: /*?lang=" not in body
    assert "Disallow: /*?*lang=" not in body
    assert "User-agent: AdsBot-Google" in body
    assert "User-agent: AdsBot-Google-Mobile" in body
    assert "Disallow: /dashboard" in body
    assert "Sitemap: " in body and "sitemap.xml" in body


def test_sitemap_includes_register_and_xhtml_hreflang():
    from app import app

    body = app.test_client().get("/sitemap.xml").get_data(as_text=True)
    assert "/register" in body
    assert "/agenzie" not in body
    assert "xmlns:xhtml=" in body
    assert 'hreflang="en"' in body
    assert "lang=en" in body


def test_landing_keyword_title_and_hreflang_cluster():
    from app import app

    html = app.test_client().get("/").get_data(as_text=True)
    assert "GEO" in html
    assert 'hreflang="en"' in html
    assert 'href="https://centropic.ai/?lang=en"' in html
    assert 'hreflang="x-default"' in html
    assert 'hreflang="it"' in html
    assert '"@type": "SoftwareApplication"' in html or '"@type":"SoftwareApplication"' in html
    assert "inLanguage" in html


def test_english_variant_self_canonical_and_schema_lang():
    from app import app

    html = app.test_client().get("/prezzi?lang=en").get_data(as_text=True)
    assert 'lang="en"' in html
    assert 'rel="canonical" href="https://centropic.ai/prezzi?lang=en"' in html
    assert "en-US" in html
    assert "BreadcrumbList" in html


def test_googlebot_clean_url_stays_italian():
    from app import app

    html = (
        app.test_client()
        .get("/", headers={"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"})
        .get_data(as_text=True)
    )
    assert 'lang="it"' in html
    assert 'rel="canonical" href="https://centropic.ai/"' in html


def test_login_noindex_register_indexable():
    from app import app

    login = app.test_client().get("/login").get_data(as_text=True)
    register = app.test_client().get("/register").get_data(as_text=True)
    assert 'name="robots" content="noindex, nofollow"' in login
    assert "noindex" not in register
    assert "GEO" in register or "AIO" in register


def test_analytics_js_has_ads_hooks():
    js = (ROOT / "static/js/analytics.js").read_text(encoding="utf-8")
    assert "persistClickIds" in js
    assert "gclid" in js
    assert "user_data" in js
    assert "adsAnalyzeSendTo" in js
    assert "analyze_start" in js
    assert "hero-url-form" in js
    assert "/anteprima" in js


def test_paddle_checkout_fires_begin_checkout():
    js = (ROOT / "static/js/paddle-checkout.js").read_text(encoding="utf-8")
    assert "begin_checkout" in js
    assert "centropicTrack" in js


def test_base_gtag_conversion_linker():
    html = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    assert "conversion_linker: true" in html
    assert "allow_enhanced_conversions: true" in html
    assert "adsAnalyzeSendTo" in html


def test_plus_and_checkout_ads_labels_wired():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "GOOGLE_ADS_PLUS_LABEL" in src
    assert "GOOGLE_ADS_CHECKOUT_LABEL" in src
    assert 'queue_analytics_event("subscribe"' in src
    assert "_ads_user_data_for" in src


def test_jsonld_partials_use_schema_language_and_nonce():
    for name in (
        "jsonld_website.html",
        "jsonld_software.html",
        "jsonld_faq.html",
        "jsonld_faq_home.html",
        "jsonld_breadcrumb.html",
    ):
        text = (ROOT / "templates/partials" / name).read_text(encoding="utf-8")
        assert 'nonce="{{ csp_nonce }}"' in text
        if name != "jsonld_breadcrumb.html":
            assert "{{ schema_in_language }}" in text
            assert '"inLanguage": "it-IT"' not in text
