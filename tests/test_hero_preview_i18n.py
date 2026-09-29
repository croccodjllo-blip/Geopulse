"""Hero lede + preview URL warning i18n (native, not Italian fallback)."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-hero-i18n")

from flask_babel import force_locale, gettext as _

from app import app, _preview_url_error_message


HERO = {
    "en": {
        "GEO e AIO in un unico score di predisposizione strutturale. Anteprima gratis, niente carta — citation monitor Misurato è su Plus.": (
            "GEO and AIO in one structural-readiness score. Free preview, no card — measured citation monitor is on Plus."
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
        "GEO e AIO in un unico score di predisposizione strutturale. Anteprima gratis, niente carta — citation monitor Misurato è su Plus.": (
            "GEO und AIO in einem Score zur strukturellen Bereitschaft. Kostenlose Vorschau, ohne Karte — gemessener Citation-Monitor ist in Plus."
        ),
        "Misura la readiness": "Miss die Bereitschaft",
        "tuodominio.it": "deine-domain.de",
        "URL non valido": "Ungültige URL",
    },
    "es": {
        "GEO e AIO in un unico score di predisposizione strutturale. Anteprima gratis, niente carta — citation monitor Misurato è su Plus.": (
            "GEO y AIO en una sola puntuación de preparación estructural. Vista previa gratis, sin tarjeta: el citation monitor Medido está en Plus."
        ),
        "Misura la readiness": "Mide la preparación",
        "tuodominio.it": "tudominio.es",
        "URL non valido": "URL no válida",
    },
    "ko": {
        "GEO e AIO in un unico score di predisposizione strutturale. Anteprima gratis, niente carta — citation monitor Misurato è su Plus.": (
            "GEO와 AIO를 하나의 구조적 준비도 점수로. 무료 미리보기, 카드 불필요 — 측정 citation 모니터는 Plus."
        ),
        "Misura la readiness": "준비도를 측정하세요",
        "tuodominio.it": "yourdomain.com",
        "URL non valido": "유효하지 않은 URL입니다",
    },
    "zh_Hans": {
        "GEO e AIO in un unico score di predisposizione strutturale. Anteprima gratis, niente carta — citation monitor Misurato è su Plus.": (
            "GEO 与 AIO 合为一个结构就绪度分数。免费预览，无需信用卡 — 实测 citation monitor 仅限 Plus。"
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
        ("en", "structural-readiness score", "yourdomain.com"),
        ("de", "strukturellen Bereitschaft", "deine-domain.de"),
        ("es", "preparación estructural", "tudominio.es"),
        ("ko", "구조적 준비도", "yourdomain.com"),
        ("zh", "结构就绪度", "yourdomain.com"),
    ]:
        r = client.get(f"/?lang={lang}")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert needle in html, (lang, needle)
        assert f'placeholder="{placeholder}"' in html, (lang, placeholder)
        assert "Anteprima gratis, niente carta" not in html
