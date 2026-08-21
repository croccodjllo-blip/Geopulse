"""Warm gold production tokens — no leftover teal/chrome accent."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
PREVIEW = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")


def test_root_tokens_are_warm_gold():
    assert "--brand-cyan: #E8A04A" in CSS
    assert "--brand-bg: #121212" in CSS
    assert "--plan-accent: #E8A04A" in CSS
    assert "#3FA8B5" not in CSS
    assert "#3FA8B5" not in PREVIEW


def test_logo_svg_is_gold_c_arcs():
    logo = (ROOT / "static" / "img" / "logo.svg").read_text(encoding="utf-8")
    assert "#E8A04A" in logo
    assert "A50 50" in logo or "A24 24" in logo
