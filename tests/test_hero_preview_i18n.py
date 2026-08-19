"""Hero lede + preview URL warning i18n (native, not Italian fallback)."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-hero-i18n")

from flask_babel import force_locale, gettext as _

from app import app, _preview_url_error_message


HERO = {
    "en": {
        "Scopri quanto il tuo sito è pronto per essere compreso, citato e raccomandato dalle intelligenze artificiali.": (
            "See how ready your site is to be understood, cited, and recommended by AI."
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
        "Scopri quanto il tuo sito è pronto per essere compreso, citato e raccomandato dalle intelligenze artificiali.": (
            "Sehen Sie, wie bereit Ihre Website ist, von KI verstanden, zitiert und empfohlen zu werden."
        ),
        "Misura la readiness": "Miss die Bereitschaft",
        "tuodominio.it": "deine-domain.de",
        "URL non valido": "Ungültige URL",
    },
    "es": {
        "Scopri quanto il tuo sito è pronto per essere compreso, citato e raccomandato dalle intelligenze artificiali.": (
            "Descubre cuán listo está tu sitio para ser comprendido, citado y recomendado por la IA."
        ),
        "Misura la readiness": "Mide la preparación",
        "tuodominio.it": "tudominio.es",
        "URL non valido": "URL no válida",
    },
    "ko": {
        "Scopri quanto il tuo sito è pronto per essere compreso, citato e raccomandato dalle intelligenze artificiali.": (
            "사이트가 AI에 이해·인용·추천될 준비가 얼마나 되었는지 확인하세요."
        ),
        "Misura la readiness": "준비도를 측정하세요",
        "tuodominio.it": "yourdomain.com",
        "URL non valido": "유효하지 않은 URL입니다",
    },
    "zh_Hans": {
        "Scopri quanto il tuo sito è pronto per essere compreso, citato e raccomandato dalle intelligenze artificiali.": (
            "了解你的网站被 AI 理解、引用和推荐的就绪程度。"
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
        ("en", "See how ready your site is", "yourdomain.com"),
        ("de", "Sehen Sie, wie bereit Ihre Website ist", "deine-domain.de"),
        ("es", "Descubre cuán listo está tu sitio", "tudominio.es"),
        ("ko", "사이트가 AI에 이해", "yourdomain.com"),
        ("zh", "了解你的网站被 AI", "yourdomain.com"),
    ]:
        r = client.get(f"/?lang={lang}")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert needle in html, (lang, needle)
        assert f'placeholder="{placeholder}"' in html, (lang, placeholder)
        assert "Scopri quanto il tuo sito è pronto" not in html
