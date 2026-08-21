"""Inner pages share the homepage warm-gold system — no charcoal plates or chrome leftovers."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
PREVIEW = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")


def test_page_intro_mark_has_no_charcoal_plate():
    start = APP.index(".page-intro__brand-mark {")
    block = APP[start : start + 280]
    assert "background: transparent" in block
    assert "background: var(--brand-bg)" not in block
    assert "border-radius: 0" in block


def test_nav_mark_has_no_charcoal_plate():
    start = APP.index(".brand-mark__logo {")
    block = APP[start : start + 280]
    assert "background: transparent" in block
    assert "box-shadow: none" in block


def test_pricing_intro_is_not_a_locked_viewport():
    start = APP.index(".page-intro--hero {")
    block = APP[start : start + 520]
    assert "min-height: 0" in block
    assert "100svh" not in block
    assert "rgba(232, 160, 74" in block
    assert "rgba(201, 211, 221" not in block


def test_flash_success_is_green_not_chrome():
    assert ".flash-success { border-color: color-mix(in srgb, #22C55E 45%, transparent); }" in APP


def test_public_inner_pages_use_marketing_shell():
    for rel in (
        "templates/about.html",
        "templates/faq.html",
        "templates/privacy.html",
        "templates/termini.html",
        "templates/cookies.html",
        "templates/dpa.html",
        "templates/contact.html",
        "templates/pricing.html",
        "templates/product.html",
    ):
        html = (ROOT / rel).read_text(encoding="utf-8")
        assert "body-marketing" in html, rel


def test_guide_svgs_are_warm_gold():
    guide = ROOT / "static" / "img" / "guide"
    for path in guide.glob("*.svg"):
        text = path.read_text(encoding="utf-8")
        assert "#3FA8B5" not in text, path.name
        assert "#C9D3DD" not in text, path.name


def test_pack_html_uses_inter_and_gold():
    art = (ROOT / "services" / "artifacts.py").read_text(encoding="utf-8")
    assert "Space Grotesk" not in art
    assert "font-family:Inter" in art
    assert "color:#E8A04A" in art
    assert "background:#121212" in art


def test_inner_pages_preview_chrome_is_charcoal():
    assert "background-color: #05070A !important" not in PREVIEW
    assert "INNER PAGES: same warm-gold system" in PREVIEW
    assert "body.body-marketing .page-intro__brand-mark" in PREVIEW
    assert "border-radius: 999px" not in PREVIEW.split("Pricing / product")[1][:240]
