"""Design audit P1: hero has no engine-name overlays; AI badge is chrome not lavender."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hero_citation_field_has_no_engine_name_overlays():
    svg = (ROOT / "templates/partials/hero_citation_field.html").read_text(
        encoding="utf-8"
    )
    for banned in (
        "CHATGPT",
        "CLAUDE",
        "PERPLEXITY",
        "GEMINI",
        "COPILOT",
        "SECTOR",
        "SCAN ACTIVE",
    ):
        assert banned not in svg, banned
    # Geometric nodes + core reactor remain.
    assert "hcf-chrome" in svg
    assert "inner hex" in svg or "L19 -11" in svg


def test_ui_badge_ai_uses_platinum_not_lavender():
    css = (ROOT / "static/css/app.css").read_text(encoding="utf-8")
    assert "#EDE9FE" not in css
    # Badge rule must use platinum/chrome text.
    start = css.index(".ui-badge--ai {")
    block = css[start : start + 220]
    assert "#E8EEF4" in block or "#C9D3DD" in block
