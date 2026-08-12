"""UI locale selection and Babel helpers for Centropic."""

from __future__ import annotations

from typing import Any

from flask import request, session

# UI locales offered in the language switcher.
# Italian is the source language for gettext catalogs.
SUPPORTED_LOCALES: dict[str, dict[str, str]] = {
    "it": {"label": "Italiano", "native": "IT", "og": "it_IT", "babel": "it"},
    "en": {"label": "English", "native": "EN", "og": "en_US", "babel": "en"},
    "de": {"label": "Deutsch", "native": "DE", "og": "de_DE", "babel": "de"},
    "es": {"label": "Español", "native": "ES", "og": "es_ES", "babel": "es"},
    "zh": {"label": "中文", "native": "中文", "og": "zh_CN", "babel": "zh_Hans"},
    "ko": {"label": "한국어", "native": "한국어", "og": "ko_KR", "babel": "ko"},
}

DEFAULT_LOCALE = "it"
LANG_COOKIE = "centropic_lang"
LANG_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year


def normalize_locale(code: str | None) -> str:
    raw = (code or "").strip().lower().replace("-", "_")
    if not raw:
        return DEFAULT_LOCALE
    if raw in SUPPORTED_LOCALES:
        return raw
    # Accept zh_cn / zh_hans → zh, en_us → en, etc.
    primary = raw.split("_", 1)[0]
    if primary in SUPPORTED_LOCALES:
        return primary
    if primary == "zh":
        return "zh"
    return DEFAULT_LOCALE


def babel_locale(code: str | None) -> str:
    loc = normalize_locale(code)
    return SUPPORTED_LOCALES[loc]["babel"]


def locale_meta(code: str | None = None) -> dict[str, str]:
    loc = normalize_locale(code)
    meta = dict(SUPPORTED_LOCALES[loc])
    meta["code"] = loc
    return meta


def select_locale() -> str:
    """Resolve active UI locale: ?lang= → session/cookie → Accept-Language → it."""
    forced = request.args.get("lang")
    if forced:
        return babel_locale(forced)

    sess = session.get("lang")
    if sess:
        return babel_locale(str(sess))

    cookie = request.cookies.get(LANG_COOKIE)
    if cookie:
        return babel_locale(cookie)

    best = request.accept_languages.best_match(
        [SUPPORTED_LOCALES[c]["babel"] for c in SUPPORTED_LOCALES]
        + list(SUPPORTED_LOCALES.keys())
    )
    if best:
        # Map babel code back to our short code.
        for code, meta in SUPPORTED_LOCALES.items():
            if best == meta["babel"] or best.startswith(code):
                return meta["babel"]
        return babel_locale(best)
    return babel_locale(DEFAULT_LOCALE)


def active_ui_locale() -> str:
    """Short UI code (it/en/de/es/zh/ko) for templates and cookies."""
    # Invert from babel locale currently selected when possible.
    from flask_babel import get_locale

    try:
        current = str(get_locale() or DEFAULT_LOCALE)
    except Exception:
        current = DEFAULT_LOCALE
    current_l = current.lower().replace("-", "_")
    for code, meta in SUPPORTED_LOCALES.items():
        if current_l == meta["babel"].lower() or current_l.startswith(code):
            return code
    return normalize_locale(current_l)


def translate_stored(message: str | None) -> str:
    """Translate a stored Italian msgid at request time.

    Use this instead of ``_(info["title"])`` so Babel does not extract the
    dict key ``title`` / ``message`` / ``hint`` as fake msgids.
    Catalog coverage comes from ``services/i18n_findings.py``.
    """
    if not message:
        return ""
    from flask_babel import gettext

    return gettext(message)


def language_switcher_items(current: str | None = None) -> list[dict[str, Any]]:
    cur = normalize_locale(current or active_ui_locale())
    items = []
    for code, meta in SUPPORTED_LOCALES.items():
        items.append(
            {
                "code": code,
                "label": meta["label"],
                "native": meta["native"],
                "active": code == cur,
            }
        )
    return items
