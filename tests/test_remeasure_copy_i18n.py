"""Re-measure / first-diagnosis confirm copy is native (not Italian fallback)."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-remeasure-i18n")

from flask_babel import force_locale

from app import app
from services.usage_billing import estimate_improvement


EXPECTED = {
    "en": {
        "label": "Re-measurement",
        "crawl": "Crawl up to 120 pages.",
        "measured": "Includes Measured SoV probes (Plus).",
        "body": "Recalculates scores and findings",
        "caveat": "not guaranteed",
    },
    "de": {
        "label": "Neuvermessung",
        "crawl": "Crawl von bis zu 120 Seiten.",
        "measured": "Measured-SoV-Probes",
        "body": "Berechnet Scores und Findings",
        "caveat": "nicht garantiert",
    },
    "es": {
        "label": "Nueva medición",
        "crawl": "Crawl de hasta 120 páginas.",
        "measured": "SoV medido",
        "body": "Recalcula puntuaciones",
        "caveat": "no hay mejora garantizada",
    },
    "ko": {
        "label": "재측정",
        "crawl": "최대 120페이지",
        "measured": "Measured SoV",
        "body": "다시 계산",
        "caveat": "보장되지 않습니다",
    },
    "zh_Hans": {
        "label": "重新测量",
        "crawl": "最多抓取 120",
        "measured": "实测 SoV",
        "body": "重新计算评分",
        "caveat": "不保证",
    },
}


def test_remeasure_confirm_copy_is_native():
    class _Site:
        aio_score = 60
        geo_score = 55

        def __init__(self) -> None:
            self.rating = {"code": "C"}

    with app.app_context():
        for loc, want in EXPECTED.items():
            with force_locale(loc):
                imp = estimate_improvement(
                    existing_site=_Site(),
                    run_measured=True,
                    crawl_pages=120,
                )
                assert imp.improvement_label == want["label"], (
                    loc,
                    imp.improvement_label,
                )
                detail = imp.improvement_detail
                assert want["crawl"] in detail, (loc, detail)
                assert want["measured"] in detail, (loc, detail)
                assert want["body"] in detail, (loc, detail)
                assert want["caveat"] in detail.lower() or want["caveat"] in detail, (
                    loc,
                    detail,
                )
                assert "Ri-misurazione" not in detail
                assert "miglioramento garantito" not in detail
