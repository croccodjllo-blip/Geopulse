"""Site guide payload + glossary integrity."""

from __future__ import annotations

from pathlib import Path

from services.site_guide import GUIDE_IMAGES, site_guide_payload

ROOT = Path(__file__).resolve().parents[1]


def test_site_guide_has_services_analyses_glossary():
    guide = site_guide_payload()
    assert guide["title"]
    assert len(guide["services"]) >= 10
    assert len(guide["analyses"]) >= 8
    assert len(guide["glossary"]) >= 20
    assert len(guide["workflow"]) >= 5
    assert all(s.get("image") for s in guide["services"])
    assert all(g.get("slug") and g.get("term") and g.get("definition") for g in guide["glossary"])
    slugs = [g["slug"] for g in guide["glossary"]]
    assert len(slugs) == len(set(slugs))
    assert "aio" in slugs and "geo" in slugs and "edge-signals" in slugs


def test_guide_illustration_files_exist():
    for key, rel in GUIDE_IMAGES.items():
        path = ROOT / "static" / rel
        assert path.is_file(), f"missing {key}: {path}"
        assert path.stat().st_size > 200
