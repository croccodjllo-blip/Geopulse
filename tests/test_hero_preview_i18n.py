"""Hero lede + preview URL warning i18n (native, not Italian fallback)."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-hero-i18n")

from flask_babel import force_locale, gettext as _

from app import app, _preview_url_error_message


HERO = {
    "en": {
        "GEO e AIO in un unico score: quanto ChatGPT, Perplexity e Google AI possono comprendere e citare il tuo brand. Anteprima gratis, niente carta.": (
            "GEO and AIO in one score: how well ChatGPT, Perplexity, and Google AI can understand and cite your brand. Free preview, no credit card."
        ),
        "Misura la visibilità GEO": "Measure GEO visibility",
        "del tuo sito per le IA": "of your site for AI",
        "Anteprima immediata · niente carta": "Instant preview · no credit card",
        "tuodominio.it": "yourdomain.com",
        "Inserisci l’URL del tuo sito (es. tuodominio.it).": (
            "Enter your site URL (e.g. yourdomain.com)."
        ),
        "URL non valido": "Invalid URL",
    },
    "de": {
        "GEO e AIO in un unico score: quanto ChatGPT, Perplexity e Google AI possono comprendere e citare il tuo brand. Anteprima gratis, niente carta.": (
            "GEO und AIO in einem Score: wie gut ChatGPT, Perplexity und Google AI deine Marke verstehen und zitieren können. Kostenlose Vorschau, ohne Karte."
        ),
        "Misura la visibilità GEO": "Miss die GEO-Sichtbarkeit",
        "tuodominio.it": "deine-domain.de",
        "URL non valido": "Ungültige URL",
    },
    "es": {
        "GEO e AIO in un unico score: quanto ChatGPT, Perplexity e Google AI possono comprendere e citare il tuo brand. Anteprima gratis, niente carta.": (
            "GEO y AIO en una sola puntuación: cuánto pueden comprender y citar tu marca ChatGPT, Perplexity y Google AI. Vista previa gratis, sin tarjeta."
        ),
        "Misura la visibilità GEO": "Mide la visibilidad GEO",
        "tuodominio.it": "tudominio.es",
        "URL non valido": "URL no válida",
    },
    "ko": {
        "GEO e AIO in un unico score: quanto ChatGPT, Perplexity e Google AI possono comprendere e citare il tuo brand. Anteprima gratis, niente carta.": (
            "하나의 점수로 보는 GEO와 AIO: ChatGPT, Perplexity, Google AI가 브랜드를 이해하고 인용할 수 있는 정도. 무료 미리보기, 카드 불필요."
        ),
        "Misura la visibilità GEO": "GEO 가시성을 측정하세요",
        "tuodominio.it": "yourdomain.com",
        "URL non valido": "유효하지 않은 URL입니다",
    },
    "zh_Hans": {
        "GEO e AIO in un unico score: quanto ChatGPT, Perplexity e Google AI possono comprendere e citare il tuo brand. Anteprima gratis, niente carta.": (
            "GEO 与 AIO 合为一个分数：ChatGPT、Perplexity 和 Google AI 能在多大程度上理解并引用你的品牌。免费预览，无需信用卡。"
        ),
        "Misura la visibilità GEO": "衡量 GEO 可见度",
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
        ("en", "GEO and AIO in one score", "yourdomain.com"),
        ("de", "GEO und AIO in einem Score", "deine-domain.de"),
        ("es", "GEO y AIO en una sola", "tudominio.es"),
        ("ko", "하나의 점수로 보는 GEO와 AIO", "yourdomain.com"),
        ("zh", "GEO 与 AIO 合为一个分数", "yourdomain.com"),
    ]:
        r = client.get(f"/?lang={lang}")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert needle in html, (lang, needle)
        assert f'placeholder="{placeholder}"' in html, (lang, placeholder)
        assert "Anteprima gratis, niente carta" not in html
