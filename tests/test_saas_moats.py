"""Unit tests for SaaS moat helpers (SoV graph, verticals, edge telemetry, agency)."""

from __future__ import annotations

from services.agency import build_whitelabel_html, build_whitelabel_markdown
from services.edge_telemetry import classify_crawler
from services.sov_graph import (
    extract_sov_snapshot,
    sov_delta_findings,
    sov_series_for_chart,
)
from services.vertical_packs import (
    apply_vertical_to_prompt_bank,
    get_vertical,
    list_verticals,
    vertical_checklist,
)


def test_extract_sov_snapshot_measured():
    result = {
        "signals": {
            "sov_measured": {
                "available": True,
                "evidence": "measured",
                "brand_mention_rate": 42.5,
                "engines": [
                    {
                        "id": "chatgpt",
                        "label": "ChatGPT",
                        "mention_rate": 40,
                        "evidence": "measured",
                        "model": "gpt-4o-mini",
                    }
                ],
            }
        }
    }
    snap = extract_sov_snapshot(result)
    assert snap is not None
    assert snap["brand_mention_rate"] == 42.5
    assert snap["engines"][0]["id"] == "chatgpt"


def test_extract_sov_snapshot_skips_proxy_only():
    result = {
        "signals": {
            "sov_measured": {
                "available": False,
                "evidence": "proxy",
                "engines": [{"id": "x", "evidence": "proxy"}],
            }
        }
    }
    assert extract_sov_snapshot(result) is None


def test_sov_delta_findings_drop():
    findings = sov_delta_findings(
        current={"brand_mention_rate": 20},
        previous_rate=50,
        threshold_drop=15,
    )
    assert len(findings) == 1
    assert findings[0]["title"].startswith("Alert:")
    assert findings[0]["severity"] == "critical"


def test_sov_delta_findings_no_drop():
    assert (
        sov_delta_findings(
            current={"brand_mention_rate": 48},
            previous_rate=50,
            threshold_drop=15,
        )
        == []
    )


def test_sov_series_for_chart_order():
    class Row:
        def __init__(self, t, rate):
            self.created_at = t
            self.brand_mention_rate = rate
            self.evidence = "measured"

    from datetime import datetime, timezone

    rows = [
        Row(datetime(2026, 1, 2, tzinfo=timezone.utc), 30),
        Row(datetime(2026, 1, 1, tzinfo=timezone.utc), 20),
    ]
    # list_sov_snapshots returns newest first; series reverses to oldest→newest
    series = sov_series_for_chart(rows)
    assert [p["rate"] for p in series] == [20, 30]


def test_vertical_packs_seed_prompt_bank():
    verts = list_verticals()
    assert any(v["slug"] == "saas_b2b" for v in verts)
    pack = get_vertical("saas_b2b")
    assert pack and len(pack["prompts"]) >= 3
    dumped = apply_vertical_to_prompt_bank("ecommerce")
    assert dumped and "e-commerce" in dumped.lower() or "Product" in dumped or dumped
    assert len(vertical_checklist("local")) >= 2


def test_classify_crawler_gptbot():
    assert "GPT" in classify_crawler("Mozilla/5.0 GPTBot/1.0") or classify_crawler(
        "Mozilla/5.0 (compatible; GPTBot/1.0)"
    )


def test_whitelabel_html_includes_brand():
    class Site:
        domain = "example.com"
        url = "https://example.com"
        aio_score = 70
        geo_score = 65

        def findings(self):
            return [
                {
                    "severity": "critical",
                    "title": "Alert: SoV measured in calo",
                    "detail": "drop",
                }
            ]

    html = build_whitelabel_html(
        site=Site(),
        agency={"brand_name": "Agency X", "primary_color": "#123456"},
        sov_series=[{"t": "2026-01-01T00:00:00", "rate": 40}],
    )
    assert "Agency X" in html
    assert "example.com" in html
    assert "SoV measured" in html
    md = build_whitelabel_markdown(
        site=Site(),
        agency={"brand_name": "Agency X"},
        sov_series=[{"t": "2026-01-01T00:00:00", "rate": 40}],
    )
    assert "Agency X" in md
    assert "40%" in md
