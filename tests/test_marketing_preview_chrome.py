"""Marketing homepage carries preview brand lockup + site chrome CSS."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_landing_is_hero_only_anteprima():
    html = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
    assert "hero-brand-lockup--preview" in html
    assert "hero--preview" in html
    assert "body-marketing--hero-only" in html
    assert "CENTROPIC" in html
    assert "logo-hero.png" in html
    assert "bg-void-chrome.jpg" in html
    assert "Scopri quanto il tuo sito è pronto" in html
    assert "https://iltuosito.it" in html
    assert "{% block footer %}" in html
    # Exact anteprima: no below-fold marketing sections
    assert "section-band" not in html
    assert "consideration set" not in html
    assert "product-shots" not in html
    assert "hero_citation_field.html" not in html


def test_logo_hero_asset_exists():
    assert (ROOT / "static" / "img" / "logo-hero.png").exists()
    assert (ROOT / "static" / "img" / "bg-void-chrome.jpg").exists()
    assert (ROOT / "static" / "img" / "bg-void-chrome-mobile.jpg").exists()


def test_base_footer_is_overridable():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "{% block footer %}" in base
    assert "css/site-preview-v3.css" in base


def test_marketing_css_full_browser_hero():
    css = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
    assert "body-marketing--hero-only" in css
    assert "100dvh" in css
    assert "100vh" in css  # Firefox fallback
    assert "overflow-x: hidden" in css
    assert "display: none !important" in css


def test_landing_uses_void_background():
    html = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
    assert "bg-void-chrome.jpg" in html
    assert "bg-void-chrome-mobile.jpg" in html
    assert "hero-signal-field.jpg" not in html


def test_mobile_preview_css():
    css = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
    assert "MOBILE = preview 3" in css
    assert "bg-void-chrome-mobile.jpg" in css
    assert "Centropic Plus" in css
