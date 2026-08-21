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
    assert rating["scale"] == ["DD", "CC", "BB", "AA"]
    assert rating["code"] == "BB"


def test_cvi_two_letter_thresholds():
    from services.rating import grade_from_score

    assert grade_from_score(0)["code"] == "DD"
    assert grade_from_score(39)["code"] == "DD"
    assert grade_from_score(40)["code"] == "CC"
    assert grade_from_score(64)["code"] == "CC"
    assert grade_from_score(65)["code"] == "BB"
    assert grade_from_score(84)["code"] == "BB"
    assert grade_from_score(85)["code"] == "AA"
    assert grade_from_score(100)["code"] == "AA"
    assert len(grade_from_score(90)["code"]) == 2


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
