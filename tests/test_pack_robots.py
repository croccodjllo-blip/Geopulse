"""Pack robots.txt should mirror live AI-crawler policy quality."""

from __future__ import annotations

from services.artifacts import build_robots_txt
from services.edge_signals import AI_CRAWLER_USER_AGENTS


def test_centropic_pack_robots_matches_live_shape():
    body = build_robots_txt(
        "https://centropic.ai/",
        {"domain": "centropic.ai"},
    )
    assert "User-agent: *" in body
    assert "Disallow: /dashboard" in body
    assert "Disallow: /admin" in body
    assert "Disallow: /crediti" in body
    assert "# Disallow: /admin" not in body  # must be active, not commented
    assert "User-agent: GPTBot" in body
    assert "User-agent: ChatGPT-User" in body
    assert "User-agent: OAI-SearchBot" in body
    assert "User-agent: meta-externalagent" in body
    assert "Sitemap: https://centropic.ai/sitemap.xml" in body
    assert "ai.txt" in body
    assert "llms.txt" in body
    for bot in AI_CRAWLER_USER_AGENTS:
        assert f"User-agent: {bot['ua']}" in body


def test_generic_site_robots_disallows_found_private_paths():
    body = build_robots_txt(
        "https://shop.example/",
        {
            "domain": "shop.example",
            "hrefs": [
                "https://shop.example/cart",
                "https://shop.example/checkout",
                "https://shop.example/products/a",
            ],
        },
    )
    assert "Disallow: /cart" in body
    assert "Disallow: /checkout" in body
    assert "Disallow: /admin" in body
    assert "User-agent: GPTBot" in body
    assert "Allow: /" in body
