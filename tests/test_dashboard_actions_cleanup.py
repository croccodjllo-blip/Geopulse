"""Dashboard CTAs: no toolkit strip; one pack download; one new-analysis entry."""

from __future__ import annotations

from pathlib import Path

DASH = Path("templates/dashboard.html").read_text(encoding="utf-8")
AUDIT = Path("templates/partials/dash_audit.html").read_text(encoding="utf-8")
SIGNAL = Path("templates/partials/dash_signal.html").read_text(encoding="utf-8")
PROMPT_OPS = Path("templates/partials/dash_prompt_ops.html").read_text(encoding="utf-8")
SHELL = Path("templates/partials/dashboard_shell.html").read_text(encoding="utf-8")


def test_toolkit_bar_removed():
    assert "plan-services" not in DASH
    assert "Toolkit Free" not in DASH
    assert "Toolkit Plus" not in DASH
    assert "Toolkit Business" not in DASH


def test_report_lead_button_soup_removed():
    assert "report-lead" not in SHELL
    assert "Scarica pack" not in SHELL
    assert "download_pack" not in SHELL


def test_single_pack_download_cta_in_deliverable():
    assert PROMPT_OPS.count("url_for('download_pack'") == 1
    assert "pack-deliverable__actions" in PROMPT_OPS
    assert "data-pack-mail-open" in PROMPT_OPS
    assert "download_pack" not in DASH
    assert "download_pack" not in SIGNAL
    assert "data-pack-mail-open" not in SIGNAL


def test_nuova_analisi_lives_in_analyze_reveal():
    assert "dash-compose" in AUDIT
    assert "dash-compose__title" in AUDIT
    assert "dash-mast" in AUDIT
    assert "dash-masthead" in AUDIT
    assert "dash-cvi" in AUDIT
    assert "dash-cvi__grade" in AUDIT
    assert "dash-cvi__score" in AUDIT
    assert "dash-cvi__mark" in AUDIT
    assert "dash-cvi__arc" in AUDIT
    assert 'data-band="{{ cvi_band }}"' in AUDIT
    assert "dash-ring--cvi" not in AUDIT
    assert "dash-command" in AUDIT
    assert "dash-sites" in AUDIT
    assert "<select" not in AUDIT
    assert "dash-rivals" in AUDIT
    assert "dash-audit__deep" in AUDIT
    assert "analyze-reveal" not in DASH
    assert "{{ _('Audit') }}" in AUDIT
    assert "{{ _('Nuova analisi') }}" not in DASH
    assert "{{ _('Nuova analisi') }}" not in AUDIT
    assert 'btn btn-ghost" href="#analyze"' not in SHELL
    assert 'btn btn-signal" href="#analyze"' not in SHELL
    assert "dash_audit.html" in DASH
