"""Smoke-check native UI chrome translations are present (not Italian fallback)."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-i18n-ui")

from flask_babel import force_locale, gettext as _

from app import app


EXPECTED = {
    "en": {
        "Accedi": "Sign in",
        "Registrati": "Sign up",
        "Analizza gratis": "Analyze free",
        "Copertura": "Coverage",
        "Prezzi": "Pricing",
        "Passa a Plus": "Upgrade to Plus",
    },
    "de": {
        "Accedi": "Anmelden",
        "Registrati": "Registrieren",
        "Analizza gratis": "Kostenlos analysieren",
        "Copertura": "Abdeckung",
        "Guida": "Leitfaden",
        "Storico": "Verlauf",
    },
    "es": {
        "Accedi": "Iniciar sesión",
        "Registrati": "Regístrate",
        "Analizza gratis": "Analizar gratis",
        "Copertura": "Cobertura",
        "Impostazioni": "Ajustes",
        "Storico": "Historial",
    },
    "ko": {
        "Accedi": "로그인",
        "Registrati": "회원가입",
        "Analizza gratis": "무료로 분석",
        "Prezzi": "요금제",
        "Chi siamo": "회사 소개",
    },
    "zh_Hans": {
        "Accedi": "登录",
        "Registrati": "注册",
        "Analizza gratis": "免费分析",
        "Prezzi": "定价",
        "Chi siamo": "关于我们",
        "Copertura": "额度",
    },
}


def test_ui_chrome_translations_are_native():
    with app.app_context():
        for loc, pairs in EXPECTED.items():
            with force_locale(loc):
                for msgid, want in pairs.items():
                    assert _(msgid) == want, (loc, msgid, _(msgid), want)
