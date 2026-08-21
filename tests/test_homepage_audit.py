"""Homepage technical + graphic audit gates (warm-gold hero)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
PREVIEW = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
BASE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")


def test_hero_copy_wraps_so_i18n_does_not_clip():
    assert "white-space: nowrap !important" not in PREVIEW.split("hero-lede")[1][:400]
    assert "white-space: normal !important" in PREVIEW
    assert "text-wrap: pretty" in PREVIEW
    assert "text-wrap: balance" in PREVIEW


def test_hero_readiness_is_translated():
    assert "{{ _('readiness') }}" in LANDING
    assert 'hero-accent">readiness' not in LANDING


def test_hero_labelled_by_headline_not_brand_lockup():
    assert 'aria-labelledby="hero-headline"' in LANDING
    assert 'id="hero-headline"' in LANDING
    assert 'aria-labelledby="hero-brand"' not in LANDING


def test_homepage_has_no_invisible_faq_jsonld():
    assert "jsonld_faq_home.html" not in LANDING
    assert "FAQPage" not in LANDING


def test_homepage_skips_paddle_js():
    assert "request.endpoint != 'index'" in BASE


def test_hero_offers_webp_and_png_fallback():
    assert "bg-hero-anteprima.webp" in LANDING
    assert "bg-hero-anteprima-mobile.webp" in LANDING
    assert "bg-hero-anteprima.png" in LANDING
    webp = ROOT / "static" / "img" / "bg-hero-anteprima.webp"
    png = ROOT / "static" / "img" / "bg-hero-anteprima.png"
    assert webp.exists() and png.exists()
    assert webp.stat().st_size < png.stat().st_size
    assert webp.stat().st_size < 700_000


def test_hero_form_keeps_csrf_and_text_url():
    assert 'name="csrf_token"' in LANDING
    assert 'type="text"' in LANDING
    assert 'name="url"' in LANDING
    assert "preview_analyze_start" in LANDING


def test_hero_logo_has_no_charcoal_plate():
    logo = (ROOT / "static" / "img" / "logo.svg").read_text(encoding="utf-8")
    mark = (ROOT / "static" / "img" / "logo-mark.svg").read_text(encoding="utf-8")
    assert 'fill="#121212"' not in logo
    assert "<rect" not in logo
    assert 'fill="#121212"' not in mark
    fav = (ROOT / "static" / "favicon.svg").read_text(encoding="utf-8")
    assert 'fill="#121212"' in fav


def test_hero_grows_instead_of_locking_viewport():
    assert "min-height: 100dvh" in PREVIEW
    locked = {line.strip() for line in PREVIEW.splitlines()}
    assert "height: 100vh;" not in locked
    assert "height: 100dvh;" not in locked
    assert "inset: 0 !important" in PREVIEW
    assert "aspect-ratio: auto !important" in PREVIEW
