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
    assert rating["band"] == "b"
    assert rating["tone"] == "#F59E0B"


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
    assert grade_from_score(0)["band"] == "d" and grade_from_score(0)["tone"] == "#EF4444"
    assert grade_from_score(40)["band"] == "c" and grade_from_score(40)["tone"] == "#F97316"
    assert grade_from_score(65)["band"] == "b" and grade_from_score(65)["tone"] == "#F59E0B"
    assert grade_from_score(85)["band"] == "a" and grade_from_score(85)["tone"] == "#22C55E"


def test_normalize_legacy_three_letter_grades():
    from services.rating import normalize_grade

    assert normalize_grade("AAA") == "AA"
    assert normalize_grade("BBB") == "BB"
    assert normalize_grade("CCC") == "CC"
    assert normalize_grade("DDD") == "DD"
    assert normalize_grade("C") == "CC"
    assert normalize_grade("aa") == "AA"


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
    assert "DD→AA" in cvi["definition"] or "DD" in cvi["definition"]
