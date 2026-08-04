"""FAQ pack JSON-LD must use real Q&A, not Cos'è + marketing H2."""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from services.artifacts import build_faq_json_ld
from services.signals import detect_html_faq, parse_json_ld_scripts


def _entities(html: str) -> list[dict]:
    m = re.search(r"<script[^>]*>(.*?)</script>", html, re.S)
    assert m
    payload = json.loads(m.group(1))
    return payload["mainEntity"]


def test_faq_does_not_wrap_marketing_headings():
    html = build_faq_json_ld(
        "https://centropic.ai/",
        {
            "domain": "centropic.ai",
            "title": "Signal Intelligence per AIO e GEO",
            "description": (
                "Centropic diagnostica citabilità AIO/GEO e genera artifact "
                "machine-readable per il dominio."
            ),
            "headings": [
                "Scopri se le IA ti citano",
                "Le IA consigliano chi è chiaro da citare.",
                "Tre fasi. Output operativo.",
                "Diagnosi, priorità, artifact.",
            ],
        },
    )
    assert "Cos’è Scopri se le IA ti citano" not in html
    assert "Cos’è Tre fasi" not in html
    assert "informazioni ufficiali su centropic.ai. Dettagli su" not in html.lower()
    ents = _entities(html)
    assert len(ents) >= 2
    names = " ".join(e["name"] for e in ents)
    assert "Scopri se le IA ti citano" not in names
    assert "Centropic" in names


def test_faq_prefers_existing_jsonld_entities():
    html = build_faq_json_ld(
        "https://centropic.ai/",
        {
            "domain": "centropic.ai",
            "title": "Centropic",
            "description": "desc",
            "headings": ["Scopri se le IA ti citano"],
            "jsonld": {
                "faq_entities": [
                    {
                        "name": "Cosa significano AIO e GEO in Centropic?",
                        "text": (
                            "AIO indica AI-Driven Visibility; GEO indica "
                            "Generative Engine Optimization."
                        ),
                    },
                    {
                        "name": "Gli score rappresentano menzioni live?",
                        "text": "No di default: sono diagnostici etichettati Stimato.",
                    },
                ]
            },
        },
    )
    assert "Cosa significano AIO e GEO in Centropic?" in html
    assert "Scopri se le IA ti citano" not in html
    assert "Cos’è Scopri" not in html


def test_parse_json_ld_extracts_faq_entities():
    scripts = [
        json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": "Cos’è Centropic?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": "Piattaforma AIO/GEO europea.",
                        },
                    }
                ],
            }
        )
    ]
    meta = parse_json_ld_scripts(scripts)
    assert meta["has_faq_page"] is True
    assert meta["faq_questions"] == 1
    assert meta["faq_entities"][0]["name"] == "Cos’è Centropic?"
    assert "AIO/GEO" in meta["faq_entities"][0]["text"]


def test_detect_html_faq_extracts_details_pairs():
    soup = BeautifulSoup(
        """
        <details>
          <summary>Cos’è AIO?</summary>
          <p>AI-Driven Visibility: quanto i modelli comprendono il brand.</p>
        </details>
        <details>
          <summary>Cos’è GEO?</summary>
          <p>Generative Engine Optimization per la citabilità nelle risposte IA.</p>
        </details>
        """,
        "lxml",
    )
    meta = detect_html_faq(soup)
    assert meta["details_questions"] == 2
    assert len(meta["pairs"]) == 2
    assert meta["pairs"][0]["name"] == "Cos’è AIO?"
    assert "AI-Driven Visibility" in meta["pairs"][0]["text"]
