"""CMS universal connector — bundle + ZIP contract."""

from __future__ import annotations

import io
import zipfile

from services.cms_connector import (
    EDGE_ROUTE_MAP,
    build_cms_bundle,
    cms_bundle_zip_bytes,
)


EDGE = "https://centropic.ai/e/tok_test123"
SITE = "https://example.com"


def test_build_cms_bundle_has_all_adapters():
    bundle = build_cms_bundle(origin_edge_base=EDGE, site_origin=SITE)
    assert bundle["schema"] == "centropic.cms_connector/v1"
    assert bundle["edge_base"] == EDGE
    assert bundle["routes"] == EDGE_ROUTE_MAP
    expected = {
        "wordpress",
        "shopify",
        "drupal",
        "generic_php",
        "netlify",
        "cloudflare",
        "vercel",
        "html_embed",
    }
    assert set(bundle["adapters"]) == expected
    wp = bundle["adapters"]["wordpress"]["files"]
    php = next(iter(wp.values()))
    assert "Plugin Name: Centropic Edge Signals" in php
    assert EDGE in php
    assert "$which = get_query_var" in php
    assert "$ wh" not in php


def test_cms_bundle_zip_contains_adapters_and_readme():
    raw = cms_bundle_zip_bytes(origin_edge_base=EDGE, site_origin=SITE)
    assert raw[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "README.md" in names
        assert "routes.json" in names
        assert any(n.startswith("wordpress/") for n in names)
        assert any(n.startswith("drupal/") for n in names)
        assert any(n.startswith("generic_php/") for n in names)
        assert any(n.endswith("INSTALL.txt") for n in names)
        readme = zf.read("README.md").decode("utf-8")
        assert EDGE in readme
        assert SITE in readme


def test_edge_route_map_covers_well_known_paths():
    assert "/llms.txt" in EDGE_ROUTE_MAP
    assert "/robots.txt" in EDGE_ROUTE_MAP
    assert "/.well-known/organization.jsonld" in EDGE_ROUTE_MAP
    assert "/geopulse/signals.json" in EDGE_ROUTE_MAP
