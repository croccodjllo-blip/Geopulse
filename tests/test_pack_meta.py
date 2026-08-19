"""Pack meta-pack.html quality: brand title, aligned canonical/OG, social tags."""

from __future__ import annotations

from services.artifacts import build_meta_pack


def test_meta_pack_brand_title_and_aligned_urls():
    html = build_meta_pack(
        "https://centropic.ai/",
        {
            "domain": "centropic.ai",
            "title": "Signal Intelligence per AIO e GEO · centropic.ai",
            "description": (
                "Centropic — Signal Intelligence per Generative Engine Optimization: "
                "diagnosi del dominio, artifact machine-readable e citabilità nelle risposte IA."
            ),
            "canonical": "https://centropic.ai",
            "lang": "it",
            "og_image": "https://centropic.ai/static/img/og-share.jpg",
        },
    )
    assert "<title>Centropic — Signal Intelligence per AIO e GEO</title>" in html
    assert 'og:site_name" content="Centropic"' in html
    assert 'og:locale" content="it_IT"' in html
    assert 'canonical" href="https://centropic.ai"' in html
    assert 'og:url" content="https://centropic.ai"' in html
    assert "og:url\" content=\"https://centropic.ai/\"" not in html
    assert "og-share.jpg" in html
    assert "twitter:card" in html
    assert "Assicurati che" not in html
    assert '<html lang="it">' in html
    assert "· centropic.ai" not in html


def test_meta_pack_keeps_brand_when_already_in_title():
    html = build_meta_pack(
        "https://centropic.ai/faq",
        {
            "domain": "centropic.ai",
            "title": "FAQ · centropic.ai",
            "description": "Domande frequenti su Centropic.",
            "lang": "it-IT",
        },
    )
    assert "<title>FAQ</title>" in html or "<title>Centropic — FAQ</title>" in html
    assert "centropic.ai" not in html.split("<title>")[1].split("</title>")[0]
    assert 'og:locale" content="it_IT"' in html
