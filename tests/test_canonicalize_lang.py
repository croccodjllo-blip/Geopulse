"""Crawl discovery must not treat /lang/* or ?next= as content pages."""

from __future__ import annotations

from services.analyzer import canonicalize_page_url


def test_canonicalize_skips_lang_switcher():
    seed = "https://centropic.ai/"
    assert canonicalize_page_url("/lang/en?next=/", seed=seed) is None
    assert canonicalize_page_url("https://centropic.ai/lang/it?next=/prezzi?", seed=seed) is None


def test_canonicalize_strips_next_and_lang_query():
    seed = "https://centropic.ai/"
    assert (
        canonicalize_page_url("https://centropic.ai/prodotto?next=/crediti", seed=seed)
        == "https://centropic.ai/prodotto"
    )
    assert (
        canonicalize_page_url("https://centropic.ai/faq?lang=en", seed=seed)
        == "https://centropic.ai/faq"
    )


def test_canonicalize_skips_auth_form_paths():
    seed = "https://centropic.ai/"
    assert canonicalize_page_url("https://centropic.ai/login?next=/crediti", seed=seed) is None
    assert canonicalize_page_url("/register", seed=seed) is None
    assert canonicalize_page_url("/recupero-password", seed=seed) is None


def test_canonicalize_keeps_benign_short_query():
    seed = "https://centropic.ai/"
    assert (
        canonicalize_page_url("https://centropic.ai/search?q=aio", seed=seed)
        == "https://centropic.ai/search?q=aio"
    )


def test_canonicalize_skips_auth_gated_app_paths():
    seed = "https://centropic.ai/"
    assert canonicalize_page_url("/crediti", seed=seed) is None
    assert canonicalize_page_url("/dashboard/storico", seed=seed) is None
