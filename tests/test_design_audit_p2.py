"""Design audit P2: token hygiene, hero asset docs, no orphan earth hero."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_design_architect_documents_signal_field_not_cosmic():
    text = (ROOT / ".cursor/rules/design-architect.mdc").read_text(encoding="utf-8")
    assert "hero-signal-field.jpg" in text
    assert "hero-cosmic.jpg" not in text


def test_hero_earth_asset_removed():
    assert not (ROOT / "static/img/hero-earth.jpg").exists()


def test_nebula_tokens_wired_into_hero_aurora():
    css = (ROOT / "static/css/app.css").read_text(encoding="utf-8")
    assert "var(--nebula-blue)" in css
    assert "var(--nebula-violet)" in css
    assert "--brand-chrome:" in css
    assert "--brand-steel:" in css


def test_jsonld_scripts_carry_csp_nonce():
    partials = list((ROOT / "templates/partials").glob("jsonld_*.html"))
    assert partials
    for path in partials:
        text = path.read_text(encoding="utf-8")
        assert 'type="application/ld+json"' in text
        assert 'nonce="{{ csp_nonce }}"' in text, path.name


def test_geo_ui_components_avoid_style_attr_width():
    """Live Charts path should not rely on style={{ width: pct% }} for credits."""
    sidebar = (ROOT / "components/Sidebar.tsx").read_text(encoding="utf-8")
    assert "style={{ width:" not in sidebar
    assert "<progress" in sidebar
    trend = (ROOT / "components/SomTrendChart.tsx").read_text(encoding="utf-8")
    assert "style={{ height" not in trend
