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
    assert "logo.svg" in html
    assert "bg-void-chrome.jpg" in html
    assert "Scopri quanto il tuo sito è pronto" in html
    assert "https://iltuosito.it" in html
    # Exact anteprima: no below-fold marketing sections
    assert "section-band" not in html
    assert "consideration set" not in html
    assert "product-shots" not in html
    assert "hero_citation_field.html" not in html
    assert "hero-visual__scan" not in html


def test_logo_is_concentric_arcs_mark():
    svg = (ROOT / "static" / "img" / "logo.svg").read_text(encoding="utf-8")
    assert svg.count("<path") >= 3
    assert 'href="' not in svg  # no external raster refs
    assert "cChrome" in svg


def test_base_loads_preview_css_sitewide():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "css/site-preview-v3.css" in base
    chunk = base.split("site-preview-v3.css", 1)[0][-200:]
    assert "current_user" not in chunk


def test_marketing_css_targets_body_marketing():
    css = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
    assert "body.body-marketing" in css
    assert "hero-brand-lockup--preview" in css
    assert "hero--preview" in css
    assert "SITE PREVIEW v3" in css
    assert "100dvh" in css
    assert "body-marketing--hero-only" in css
    assert "filter: none !important" in css


def test_void_background_assets_exist():
    assert (ROOT / "static" / "img" / "bg-void-chrome.jpg").exists()
    assert (ROOT / "static" / "img" / "bg-void-chrome-mobile.jpg").exists()


def test_landing_uses_void_background():
    html = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
    assert "bg-void-chrome.jpg" in html
    assert "bg-void-chrome-mobile.jpg" in html
    assert "hero-signal-field.jpg" not in html


def test_mobile_preview_css():
    css = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
    assert "MOBILE = preview 3" in css
    assert "bg-void-chrome-mobile.jpg" in css
    assert "Dominio analizzato" not in css
    assert "Centropic Plus" in css
