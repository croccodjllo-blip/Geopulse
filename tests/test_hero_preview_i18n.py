"""Hero lede + preview URL warning i18n (native, not Italian fallback)."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-hero-i18n")

from flask_babel import force_locale, gettext as _

from app import app, _preview_url_error_message


HERO = {
    "en": {
        "Inserisci il dominio per score AIO/GEO di predisposizione strutturale e criticità.": (
            "Enter your domain for AIO/GEO structural readiness scores and critical issues."
        ),
        "Misura la readiness": "Measure readiness",
        "del tuo sito per le IA": "of your site for AI",
        "Anteprima immediata · niente carta": "Instant preview · no credit card",
        "tuodominio.it": "yourdomain.com",
        "Inserisci l’URL del tuo sito (es. tuodominio.it).": (
            "Enter your site URL (e.g. yourdomain.com)."
        ),
        "URL non valido": "Invalid URL",
    },
    "de": {
        "Inserisci il dominio per score AIO/GEO di predisposizione strutturale e criticità.": (
            "Geben Sie Ihre Domain ein — für AIO/GEO-Scores zur strukturellen Bereitschaft und kritische Befunde."
        ),
        "Misura la readiness": "Miss die Bereitschaft",
        "tuodominio.it": "deine-domain.de",
        "URL non valido": "Ungültige URL",
    },
    "es": {
        "Inserisci il dominio per score AIO/GEO di predisposizione strutturale e criticità.": (
            "Introduce tu dominio para obtener puntuaciones AIO/GEO de preparación estructural y criticidades."
        ),
        "Misura la readiness": "Mide la preparación",
        "tuodominio.it": "tudominio.es",
        "URL non valido": "URL no válida",
    },
    "ko": {
        "Inserisci il dominio per score AIO/GEO di predisposizione strutturale e criticità.": (
            "도메인을 입력하면 AIO/GEO 구조적 준비도 점수와 핵심 이슈를 확인할 수 있습니다."
        ),
        "Misura la readiness": "준비도를 측정하세요",
        "tuodominio.it": "yourdomain.com",
        "URL non valido": "유효하지 않은 URL입니다",
    },
    "zh_Hans": {
        "Inserisci il dominio per score AIO/GEO di predisposizione strutturale e criticità.": (
            "输入域名，即可查看 AIO/GEO 结构就绪度评分与关键问题。"
        ),
        "Misura la readiness": "衡量就绪度",
        "del tuo sito per le IA": "让你的网站面向 AI",
        "tuodominio.it": "yourdomain.com",
        "URL non valido": "无效的 URL",
    },
}


def test_hero_lede_and_url_warnings_are_native():
    with app.app_context():
        for loc, pairs in HERO.items():
            with force_locale(loc):
                for msgid, want in pairs.items():
                    got = _(msgid)
                    assert got == want, (loc, msgid, got, want)
                    assert got != msgid


def test_preview_url_error_helper_translates():
    with app.app_context():
        with force_locale("en"):
            assert _preview_url_error_message(ValueError("URL non valido")) == "Invalid URL"
            assert "resolved" in _preview_url_error_message(
                ValueError("Host non risolvibile: bad.example")
            ).lower() or "could not" in _preview_url_error_message(
                ValueError("Host non risolvibile: bad.example")
            ).lower()
            assert "not allowed" in _preview_url_error_message(
                ValueError("Indirizzo IP non pubblico: 127.0.0.1")
            ).lower()


def test_landing_hero_html_localized():
    client = app.test_client()
    for lang, needle, placeholder in [
        ("en", "Enter your domain for AIO/GEO", "yourdomain.com"),
        ("de", "Geben Sie Ihre Domain ein", "deine-domain.de"),
        ("es", "Introduce tu dominio", "tudominio.es"),
        ("ko", "도메인을 입력하면", "yourdomain.com"),
        ("zh", "输入域名", "yourdomain.com"),
    ]:
        r = client.get(f"/?lang={lang}")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert needle in html, (lang, needle)
        assert f'placeholder="{placeholder}"' in html, (lang, placeholder)
        assert "Inserisci il dominio per score" not in html
