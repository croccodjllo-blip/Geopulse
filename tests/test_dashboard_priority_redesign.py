"""Dashboard priority redesign: signal deck, no fold clutter."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
SIGNAL = (ROOT / "templates" / "partials" / "dash_signal.html").read_text(
    encoding="utf-8"
)
SHELL = (ROOT / "templates" / "partials" / "dashboard_shell.html").read_text(
    encoding="utf-8"
)
CSS = (ROOT / "static" / "css" / "site-preview-v3.css").read_text(encoding="utf-8")
DYN = (ROOT / "templates" / "partials" / "dash_dynamic_styles.html").read_text(
    encoding="utf-8"
)


def test_preview_css_linked():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "site-preview-v3.css" in base
    # Site-wide (marketing + auth + dash), not gated on current_user.
    assert "{% if current_user %}" not in base.split("site-preview-v3.css")[0][-80:]


def test_priority_signal_deck_and_rail():
    assert "dash_signal.html" in DASH
    assert 'class="dash-signal"' in SIGNAL
    assert "dash-spine" in SIGNAL
    assert "dash-orbit" in SIGNAL
    assert "dash-fault" in SIGNAL
    assert "dash-meridian" in SIGNAL
    assert "dash-actions__btn" in SIGNAL
    assert "dash-deck" in DASH
    assert "dash-more--ops" not in DASH
    assert "<details" not in DASH
    assert "dash-ring--cvi" not in DASH
    assert "dash-ring--sov" not in SIGNAL
    # SoV table + Findings live on /dashboard/sov (sidebar section).
    assert "dash-sov-list" not in DASH
    assert "dashboard_sov" in SIGNAL


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
    assert ".dash-signal" in CSS
    assert ".dash-spine__grade" in CSS
    assert ".dash-sov-list" in CSS
    assert ".dash-cta__primary" in CSS
    assert ".dash-detail" in CSS
    assert ".dash-orbit__sat" in CSS


def test_rail_overrides_wide_sidebar_margin():
    """Dock width must replace app.css 16rem main offset (else content hugs right)."""
    assert "--sidebar-w: 14.75rem" in CSS
    assert "--sidebar-w: 4.35rem" in CSS
    assert 'html[data-dock="rail"]' in CSS
    assert "margin-left: var(--sidebar-w) !important" in CSS
    assert "width: calc(100% - var(--sidebar-w)) !important" in CSS
    assert "max-width: calc(100% - var(--sidebar-w)) !important" in CSS
    shell = CSS.split("Global app shell", 1)[1].split("body.app-shell .app-sidebar--dock", 1)[0]
    assert "padding-left: var(--sidebar-w)" not in shell


def test_dynamic_styles_share_bars():
    assert "--share" in DYN
    assert "pulse-core" not in DYN
    assert "dash-signal" in DYN
