"""Dashboard Avvia / Salva / monitoring / analysis notes must localize natively."""

from __future__ import annotations

from flask_babel import force_locale

from app import AnalyzeForm, RescanScheduleForm, app
from services.i18n import babel_locale, translate_analysis_notes

EXPECTED = {
    "en": {
        "Avvia": "Start",
        "Salva": "Save",
        "Disattivato": "Off",
        "Ogni giorno": "Every day",
        "Ogni settimana": "Every week",
        "Monitoraggio": "Monitoring",
    },
    "de": {
        "Avvia": "Starten",
        "Salva": "Speichern",
        "Disattivato": "Aus",
        "Ogni giorno": "Täglich",
        "Ogni settimana": "Wöchentlich",
        "Monitoraggio": "Monitoring",
    },
    "es": {
        "Avvia": "Iniciar",
        "Salva": "Guardar",
        "Disattivato": "Desactivado",
        "Ogni giorno": "Cada día",
        "Ogni settimana": "Cada semana",
        "Monitoraggio": "Monitorización",
    },
    "zh": {
        "Avvia": "开始",
        "Salva": "保存",
        "Disattivato": "关闭",
        "Ogni giorno": "每天",
        "Ogni settimana": "每周",
        "Monitoraggio": "监控",
    },
    "ko": {
        "Avvia": "시작",
        "Salva": "저장",
        "Disattivato": "끔",
        "Ogni giorno": "매일",
        "Ogni settimana": "매주",
        "Monitoraggio": "모니터링",
    },
}

NOTES_IT = "Analisi dominio centropic.ai: 30 pagine · suite AIO/GEO completa."
NOTES_EXPECTED = {
    "en": "Domain analysis centropic.ai: 30 pages · full AIO/GEO suite.",
    "de": "Domainanalyse centropic.ai: 30 Seiten · vollständige AIO/GEO-Suite.",
    "es": "Análisis del dominio centropic.ai: 30 páginas · suite AIO/GEO completa.",
    "zh": "域名分析 centropic.ai：30 个页面 · 完整 AIO/GEO 套件。",
    "ko": "도메인 분석 centropic.ai: 30페이지 · 전체 AIO/GEO 스위트.",
}

SOV_NOTE = (
    "ChatGPT / Perplexity / Claude / Gemini API / Grok / Azure OpenAI: "
    "mention rate da prompt pack. Non è AI Overview o Copilot nativo, "
    "né ranking garantito nelle risposte live."
)


def test_analyze_form_submit_label_avvia():
    with app.test_request_context():
        with force_locale("en"):
            form = AnalyzeForm()
            assert str(form.submit.label.text) == "Start"
        with force_locale("it"):
            form = AnalyzeForm()
            assert str(form.submit.label.text) == "Avvia"


def test_rescan_choices_and_save_localized():
    with app.test_request_context():
        with force_locale("en"):
            form = RescanScheduleForm()
            labels = {str(c[1]) for c in form.interval.choices}
            assert "Off" in labels
            assert "Every day" in labels
            assert "Every week" in labels
            assert str(form.submit.label.text) == "Save"
        with force_locale("de"):
            form = RescanScheduleForm()
            labels = {str(c[1]) for c in form.interval.choices}
            assert "Aus" in labels
            assert "Täglich" in labels
            assert str(form.submit.label.text) == "Speichern"


def test_dashboard_ui_native_not_italian():
    with app.app_context():
        for loc, want in EXPECTED.items():
            with force_locale(babel_locale(loc)):
                from flask_babel import gettext as _

                for msgid, msgstr in want.items():
                    assert _(msgid) == msgstr, f"{loc}: {msgid}"
                note = _(SOV_NOTE)
                assert note != SOV_NOTE, f"{loc}: SoV note still Italian"


def test_translate_analysis_notes_parameterized():
    with app.app_context():
        for loc, want in NOTES_EXPECTED.items():
            with force_locale(babel_locale(loc)):
                assert translate_analysis_notes(NOTES_IT) == want, loc


def test_shell_uses_form_submit_not_hardcoded_analizza():
    from pathlib import Path

    shell = Path("templates/partials/dashboard_shell.html").read_text(encoding="utf-8")
    assert "form.submit(" in shell
    assert "Analizza dominio" not in shell
    assert 'SubmitField(_l("Avvia"))' in Path("app.py").read_text(encoding="utf-8")
