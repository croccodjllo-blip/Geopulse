"""Dashboard priority redesign: preview rings, SoV list, no fold clutter."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
SHELL = (ROOT / "templates" / "partials" / "dashboard_shell.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
DYN = (ROOT / "templates" / "partials" / "dash_dynamic_styles.html").read_text(encoding="utf-8")


def test_preview_css_linked():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "site-preview-v3.css" in base
    # Site-wide (marketing + auth + dash), not gated on current_user.
    assert "{% if current_user %}" not in base.split("site-preview-v3.css")[0][-80:]


def test_priority_hero_rings_and_micro_metrics():
    assert 'class="dash-hero"' in DASH
    assert "dash-ring--cvi" in DASH
    assert "dash-ring--sov" in DASH
    assert "dash-ring__svg" in DASH
    assert 'class="dash-micro"' in DASH
    assert "dash-actions__btn" in DASH
    assert "dash_atelier.html" in DASH
    assert "dash-more--ops" in DASH
    assert "dash-ring__meta--cvi" in DASH
    # SoV table + Findings live on /dashboard/sov (sidebar section).
    assert "dash-sov-list" not in DASH
    assert "dashboard_sov" in DASH


def test_score_sov_tabs_and_pulse_removed():
    assert 'data-tab="score"' not in DASH
    assert 'id="panel-score"' not in DASH
    assert "pulse-core" not in DASH
    assert "signal-diag" not in DASH
    assert "sov-columns" not in DASH
    assert "sov-table" not in DASH


def test_no_rail_and_solo_grid():
    assert "workspace-rail" not in DASH
    assert "workspace-grid--rail" not in DASH
    assert "workspace-strip--preview" in DASH


def test_analyze_below_fold_when_latest():
    assert "analyze_form.html" in DASH
    assert 'id="analyze-panel"' in DASH
    assert "analyze-reveal" not in SHELL
    assert "analyze_form.html" in SHELL  # empty-state path


def test_redesign_css_present():
    assert ".dash-ring__viz" in CSS
    assert ".dash-sov-list" in CSS
    assert ".dash-cta__primary" in CSS
    assert ".dash-detail" in CSS
    assert "dash-ring__meta--cvi" in CSS


def test_rail_overrides_wide_sidebar_margin():
    """Narrow icon rail must replace app.css 16rem main offset (else content hugs right)."""
    assert "--sidebar-w: 4.5rem" in CSS
    assert "margin-left: var(--sidebar-w) !important" in CSS
    assert "width: calc(100% - var(--sidebar-w)) !important" in CSS
    assert "max-width: calc(100% - var(--sidebar-w)) !important" in CSS
    # Must not stack padding-left on top of the wide-sidebar margin.
    shell = CSS.split("Global app shell", 1)[1].split("body.app-shell .app-sidebar--rail", 1)[0]
    assert "padding-left: var(--sidebar-w)" not in shell


def test_dynamic_styles_share_bars():
    assert "--share" in DYN
    assert "pulse-core" not in DYN
