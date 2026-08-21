"""Marketing homepage carries preview brand lockup + site chrome CSS."""

from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_landing_is_hero_only_anteprima():
    html = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
    assert "hero-brand-lockup--preview" in html
    assert "hero--preview" in html
    assert "body-marketing--hero-only" in html
    assert "img/logo.svg" in html
    assert "hero-brand-word" in html
    assert "bg-hero-anteprima.png" in html
    assert "bg-hero-anteprima-mobile.png" in html
    assert "Space+Grotesk" not in html and "Space Grotesk" not in html
    assert "Scopri quanto il tuo sito è pronto" in html
    assert "https://iltuosito.it" in html
    # Footer uses default base block (same as other pages)
    assert "{% block footer %}" not in html
    # Exact anteprima: no below-fold marketing sections
    assert "section-band" not in html
    assert "consideration set" not in html
    assert "product-shots" not in html
    assert "hero_citation_field.html" not in html


def test_anteprima_scale_measures_in_css():
    """Compact lockup on full-bleed nebula; form cleared from the fold; no cite-scrim."""
    css = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
    assert "--hero-band" in css
    assert "min(36rem" in css
    assert "72rem" in css  # header inner still tracks site content width
    assert "object-fit: cover !important" in css
    assert "hero-visual--preview::before" in css
    assert "filter: none !important" in css  # no shadow over logo / wordmark
    assert "clamp(5.25rem, 12vw, 7.5rem)" in css
    assert "clamp(4.75rem, 9vh, 6.5rem)" in css  # air between URL bar and footer
    locked = {line.strip() for line in css.splitlines()}
    assert "height: 100vh;" not in locked
    assert "height: 100dvh;" not in locked
    assert "white-space: normal !important" in css
    assert "max-width: 24ch" not in css
    assert "body.body-marketing--hero-only .site-footer" not in css
    assert "aspect-ratio: 16 / 9" not in css


def test_landing_uses_hero_bg():
    html = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
    assert "bg-hero-anteprima.png" in html
    assert "bg-hero-anteprima-mobile.png" in html
    assert "hero-visual__photo" in html
    desk = ROOT / "static" / "img" / "bg-hero-anteprima.png"
    mob = ROOT / "static" / "img" / "bg-hero-anteprima-mobile.png"
    assert desk.exists() and mob.exists()
    desk_w, _desk_h = _png_size(desk)
    mob_w, mob_h = _png_size(mob)
    assert desk_w >= 1200
    assert mob_h >= mob_w  # portrait


def test_logo_assets_exist():
    svg = (ROOT / "static" / "img" / "logo.svg").read_text(encoding="utf-8")
    assert "#E8A04A" in svg
    assert "cWarm" in svg or "linearGradient" in svg
    assert (ROOT / "static" / "img" / "logo-mark.svg").exists()


def test_base_footer_is_overridable():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "{% block footer %}" in base
    assert "css/site-preview-v3.css" in base


def test_flush_main_wins_max_width():
    """Regression: .site-main max-width rule must not override --flush."""
    css = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    flush_pos = css.find(".site-main.site-main--flush")
    shared_pos = css.find(".site-header__inner,\n.site-main,\n.site-footer__inner")
    assert flush_pos > shared_pos > -1
    preview = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
    assert "site-main.site-main--flush" in preview


def test_landing_uses_void_background():
    html = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
    assert "bg-hero-anteprima.png" in html
    assert "hero-signal-field.jpg" not in html
    assert "background: #121212 !important" in css
    assert "background: #000 !important" not in css
    assert "body-marketing--hero-only" in html


def test_mobile_preview_css():
    css = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
    assert "MOBILE = preview 3" in css
    assert "Centropic Plus" in css


def test_homepage_hides_nav_analizza_gratis():
    css = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
    assert "body.body-marketing--hero-only .nav-cta" in css
    assert "display: none !important" in css
