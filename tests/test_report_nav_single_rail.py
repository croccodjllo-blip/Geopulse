"""Dashboard report chrome: priority action nav, no Score/SoV tab pair."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
SIGNAL = (ROOT / "templates" / "partials" / "dash_signal.html").read_text(
    encoding="utf-8"
)
SHELL = (ROOT / "static" / "js" / "shell.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")


def test_no_duplicate_report_tabs_segment():
    assert 'class="report-tabs"' not in DASH
    assert "report-tabs__btn" not in DASH
    assert ".report-tabs" not in CSS
    assert "report-tabs__btn" not in SHELL


def test_report_nav_tabs_replaced_by_dash_actions():
    assert 'data-tab="sov"' not in DASH
    assert 'data-tab="score"' not in DASH
    assert 'class="report-nav"' not in DASH
    assert "dash-actions" in SIGNAL
    assert "{{ _('Findings') }}" in SIGNAL
    assert "{{ _('Edge') }}" in SIGNAL
    assert "{{ _('Pack') }}" in SIGNAL


def test_shell_keeps_activate_report_view_harmless():
    """Legacy shell helpers may remain; tabs are gone from markup."""
    assert "report-tabs__btn" not in SHELL
    assert 'data-tab="score"' not in DASH
