"""Column chart geometry for dashboard SoV (replaces radar UI)."""

from __future__ import annotations

from services.engine_breakdown import _column_geometry, compute_engine_breakdown


def test_column_geometry_scales_with_propensity():
    engines = [
        {"label": "A", "propensity": 100, "accent": "#111"},
        {"label": "B", "propensity": 50, "accent": "#222"},
        {"label": "C", "propensity": 0, "accent": "#333"},
    ]
    cols = _column_geometry(engines)
    assert len(cols["bars"]) == 3
    assert cols["bars"][0]["h"] > cols["bars"][1]["h"]
    assert cols["bars"][2]["h"] == 0
    assert cols["bars"][0]["value"] == 100
    assert cols["bars"][1]["value"] == 50


def test_compute_breakdown_includes_columns():
    out = compute_engine_breakdown(
        aio_score=70,
        geo_score=60,
        findings=[],
        robots_text="User-agent: *\nAllow: /\n",
    )
    assert out.get("columns") and out["columns"].get("bars")
    assert all("accent" in b for b in out["columns"]["bars"])
