"""Centropic Visibility Index (CVI) must appear in public methodology surfaces."""

from __future__ import annotations

from services.rating import compute_rating
from services.guides import _guide_metodologia, _guide_score_vs_sov
from services.site_guide import _glossary_entries


def test_rating_exposes_cvi_metric_fields():
    rating = compute_rating(80, 80, [])
    assert rating["metric"] == "CVI"
    assert rating["metric_name"] == "Centropic Visibility Index"
    assert rating["code"] in rating["scale"]


def test_metodologia_defines_cvi():
    body = _guide_metodologia()["body"]
    assert "Centropic Visibility Index" in body
    assert "CVI" in body
    assert "citation share" in body.lower() or "Citation share" in body


def test_score_vs_sov_guide_is_cvi_framed():
    guide = _guide_score_vs_sov()
    assert "CVI" in guide["title"]
    assert "Centropic Visibility Index" in guide["body"]


def test_glossary_leads_with_cvi():
    entries = _glossary_entries()
    slugs = [e["slug"] for e in entries]
    assert "cvi" in slugs
    cvi = next(e for e in entries if e["slug"] == "cvi")
    assert "CVI" in cvi["term"]
    assert "Centropic Visibility Index" in cvi["definition"] or "Centropic" in cvi["definition"]
