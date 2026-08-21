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
    assert "cvi" in slugs and "indice-criticita" in slugs and "workspace" in slugs
    assert len(guide["workspace"]["pages"]) == 5
    assert any(t["id"] == "workspace" for t in guide["toc"])
    assert "2026" in guide["updated"]
    pack = next(s for s in guide["services"] if s["id"] == "svc-pack")
    assert "centropic-fix.html" in " ".join(pack["bullets"])
    assert any(s["id"] == "svc-storico" for s in guide["services"])
    cvi = next(g for g in guide["glossary"] if g["slug"] == "cvi")
    assert "DD" in cvi["definition"] and "AA" in cvi["definition"]


def test_site_guide_english_workspace_titles():
    from flask_babel import force_locale

    from app import app

    with app.app_context():
        with force_locale("en"):
            guide = site_guide_payload()
    assert guide["workspace"]["title"] == "The five pages"
    assert [p["title"] for p in guide["workspace"]["pages"]] == [
        "Overview",
        "Benchmark",
        "Prompt",
        "Trend",
        "Guide",
    ]
    assert "yourdomain.com/llms.txt" in guide["workflow"][3]["body"]


def test_guide_hero_shows_current_workspace():
    svg = (ROOT / "static" / "img" / "guide" / "dashboard.svg").read_text(encoding="utf-8")
    assert "Panoramica" in svg
    assert "Indice di criticità" in svg
    assert "AA" in svg
    assert 'd="M102 30 A50 50 0 1 0 102 98"' in svg
    assert "icon rail" not in svg
    assert ">B</text>" not in svg
    html = (ROOT / "templates" / "guide.html").read_text(encoding="utf-8")
    assert "workspace--wide" in html
    assert "img/guide/dashboard.svg" in html or "guide.services[0].image" in html


def test_public_guide_is_fresh_and_current():
    from app import app

    client = app.test_client()
    resp = client.get("/guida")
    assert resp.status_code == 200
    assert "no-store" in (resp.headers.get("Cache-Control") or "")
    html = resp.get_data(as_text=True)
    assert "Le cinque pagine" in html or "The five pages" in html
    assert "img/guide/dashboard.svg" in html
    assert "icon rail" not in html


def test_guide_illustration_files_exist():
    for key, rel in GUIDE_IMAGES.items():
        path = ROOT / "static" / rel
        assert path.is_file(), f"missing {key}: {path}"
        assert path.stat().st_size > 200
