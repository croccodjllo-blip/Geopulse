"""Marketing homepage carries preview brand lockup + site chrome CSS."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_landing_is_hero_only_anteprima():
    html = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
    assert "hero-brand-lockup--preview" in html
    assert "hero--preview" in html
    assert "body-marketing--hero-only" in html
    assert "logo-hero.png" in html
    assert "wordmark-hero.png" in html
    assert "bg-hero-anteprima.png" not in html
    assert "bg-hero-anteprima-mobile.png" not in html
    assert "Space+Grotesk" in html or "Space Grotesk" in html
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
    """Shared hero band; void-black hero (no bg photo); no cite-scrim."""
    css = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
    assert "17.8vw" in css
    assert "52vw" in css
    assert "--hero-band" in css
    assert "66vw" in css
    assert "hero-visual--preview::before" in css
    assert "filter: none !important" in css  # no shadow over logo / wordmark
    assert ("4.5vw" in css or "3.8vw" in css)  # lockup gap keeps logo clear
    assert "white-space: nowrap !important" in css
    assert "max-width: 24ch" not in css
    assert "body.body-marketing--hero-only .site-footer" not in css
    # Hero bg photo removed — void black only
    assert "hero-visual--preview .hero-visual__photo" in css
    assert "display: none !important" in css


def test_landing_has_no_hero_bg_photo():
    html = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
    assert "bg-hero-anteprima.png" not in html
    assert "bg-hero-anteprima-mobile.png" not in html
    assert "hero-visual__photo" not in html
    assert "<picture>" not in html


def test_logo_assets_exist():
    assert (ROOT / "static" / "img" / "logo-hero.png").exists()
    assert (ROOT / "static" / "img" / "wordmark-hero.png").exists()
    from PIL import Image

    im = Image.open(ROOT / "static" / "img" / "logo-hero.png")
    assert im.size[0] >= 250
    bright = sum(
        1
        for y in range(0, im.size[1], 4)
        for x in range(0, im.size[0], 4)
        if sum(im.getpixel((x, y))[:3]) > 100
    )
    assert bright > 200


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
    assert "bg-hero-anteprima.png" not in html
    assert "hero-signal-field.jpg" not in html
    assert "background: #000 !important" in css
    assert "body-marketing--hero-only" in html


def test_mobile_preview_css():
    css = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
    assert "MOBILE = preview 3" in css
    assert "Centropic Plus" in css
