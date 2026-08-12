"""Dashboard report chrome: one sticky rail, no duplicate Score/SoV tabs."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "templates" / "dashboard.html").read_text(encoding="utf-8")
SHELL = (ROOT / "static" / "js" / "shell.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")


def test_no_duplicate_report_tabs_segment():
    assert 'class="report-tabs"' not in DASH
    assert "report-tabs__btn" not in DASH
    assert ".report-tabs" not in CSS
    assert "report-tabs__btn" not in SHELL


def test_report_nav_keeps_score_sov_and_sections():
    assert 'class="report-nav"' in DASH
    assert 'data-tab="sov"' in DASH
    assert 'data-tab="score"' in DASH
    assert "{{ _('Findings') }}" in DASH
    assert "{{ _('Edge') }}" in DASH
    assert "{{ _('Pack') }}" in DASH
    assert "report-nav__rule" in DASH
    assert "report-nav__view" in DASH


def test_shell_switches_views_via_report_nav():
    assert "activateReportView" in SHELL
    assert ".report-nav__view[data-tab]" in SHELL
    assert "report-tabs__btn" not in SHELL
