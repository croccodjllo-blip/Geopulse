"""Organization pack JSON-LD uses brand name, not hostname."""

from __future__ import annotations

import json
import re

from services.artifacts import build_json_ld


def _payload(html: str) -> dict:
    m = re.search(r"<script[^>]*>(.*?)</script>", html, re.S)
    assert m
    return json.loads(m.group(1))


def test_org_jsonld_uses_centropic_brand_not_hostname():
    html = build_json_ld(
        "https://centropic.ai/",
        {
            "domain": "centropic.ai",
            "title": "Signal Intelligence per AIO e GEO · centropic.ai",
            "description": (
                "Centropic — Signal Intelligence per Generative Engine Optimization."
            ),
        },
    )
    data = _payload(html)
    assert data["@type"] == "Organization"
    assert data["name"] == "Centropic"
    assert data["name"] != "centropic.ai"
    assert data["@id"] == "https://centropic.ai/#organization"
    assert "centropic.ai" not in data["slogan"]
    assert "Signal Intelligence" in data["slogan"]


def test_org_jsonld_reuses_crawled_organization_node():
    html = build_json_ld(
        "https://centropic.ai/",
        {
            "domain": "centropic.ai",
            "title": "Signal Intelligence · centropic.ai",
            "description": "fallback desc",
            "jsonld": {
                "org_nodes": [
                    {
                        "@type": "Organization",
                        "@id": "https://centropic.ai/#organization",
                        "name": "centropic.ai",  # bad hostname — must be rewritten
                        "url": "https://centropic.ai/",
                        "description": "Centropic SaaS AIO/GEO.",
                        "slogan": "Bringing Order to Intelligence.",
                        "email": "info@centropic.ai",
                        "sameAs": ["https://www.engineeringfactory.app/"],
                        "logo": {
                            "@type": "ImageObject",
                            "url": "https://centropic.ai/static/img/logo.png",
                        },
                    }
                ]
            },
        },
    )
    data = _payload(html)
    assert data["name"] == "Centropic"
    assert data["email"] == "info@centropic.ai"
    assert data["slogan"] == "Bringing Order to Intelligence."
    assert data["logo"]["url"].endswith("/logo.png")
    assert "engineeringfactory.app" in data["sameAs"][0]
