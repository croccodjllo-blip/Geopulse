from __future__ import annotations


def test_supported_locales_include_requested_languages():
    from services.i18n import SUPPORTED_LOCALES, normalize_locale

    for code in ("it", "en", "de", "es", "zh", "ko"):
        assert code in SUPPORTED_LOCALES
        assert normalize_locale(code) == code
    assert normalize_locale("zh_CN") == "zh"
    assert normalize_locale("en-US") == "en"


def test_set_language_persists_cookie_and_session():
    from app import app, LANG_COOKIE

    with app.test_client() as client:
        resp = client.get("/lang/de?next=/prezzi", follow_redirects=False)
        assert resp.status_code in {302, 303}
        assert LANG_COOKIE in resp.headers.get("Set-Cookie", "")
        assert "centropic_lang=de" in resp.headers.get("Set-Cookie", "")
        with client.session_transaction() as sess:
            assert sess.get("lang") == "de"


def test_english_home_translates_nav():
    from app import app

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["lang"] = "en"
        html = client.get("/").get_data(as_text=True)
        assert 'lang="en"' in html
        # Italian source should be replaced for common nav labels
        assert "Product" in html or "Prodotto" not in html
        assert "lang-switch" in html
