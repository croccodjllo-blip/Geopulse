"""Centropic Visibility Index (CVI): composite grade DD (worst) → AA (best).

CVI is the proprietary umbrella metric: composite of AIO + GEO scores with
finding penalties. Letter codes are two characters only (DD, CC, BB, AA).
Each code maps to one semantic tone used by the dashboard lockup and tables.
"""

from __future__ import annotations

from typing import Any

# Scala ordinata dal peggiore al migliore — solo due lettere.
RATING_SCALE: list[tuple[str, int, str]] = [
    ("DD", 0, "Critico — segnali AIO/GEO assenti o bloccati"),
    ("CC", 40, "Insufficiente — struttura utile ma con gap ampi"),
    ("BB", 65, "Solido — buona base, margini di rafforzamento"),
    ("AA", 85, "Eccellente — superficie machine-readable quasi completa"),
]

RATING_ORDER = [code for code, _, _ in RATING_SCALE]

# Tone hex = semantic state colors (danger / orange / warn / ok).
RATING_TONES: dict[str, dict[str, str]] = {
    "DD": {"band": "d", "tone": "#EF4444"},
    "CC": {"band": "c", "tone": "#F97316"},
    "BB": {"band": "b", "tone": "#F59E0B"},
    "AA": {"band": "a", "tone": "#22C55E"},
}

_LEGACY_CODES = {
    "DDD": "DD",
    "CCC": "CC",
    "BBB": "BB",
    "AAA": "AA",
    "D": "DD",
    "C": "CC",
    "B": "BB",
    "A": "AA",
}


def normalize_grade(code: str | None) -> str:
    """Collapse leftover 1- or 3-letter codes onto the two-letter scale."""
    raw = str(code or "").strip().upper()
    if raw in RATING_TONES:
        return raw
    return _LEGACY_CODES.get(raw, raw)


def composite_score(
    aio_score: int | None,
    geo_score: int | None,
    findings: list[dict[str, Any]] | None = None,
) -> int:
    """Media AIO / GEO con penalità sui findings critical/warn."""
    aio = 0 if aio_score is None else max(0, min(100, int(aio_score)))
    geo = 0 if geo_score is None else max(0, min(100, int(geo_score)))
    base = round((aio + geo) / 2)

    penalty = 0
    for item in findings or []:
        severity = str(item.get("severity") or "").lower()
        if severity == "critical":
            penalty += 4
        elif severity == "warn":
            penalty += 1

    return max(0, min(100, base - penalty))


def grade_from_score(score: int) -> dict[str, Any]:
    """Return CVI two-letter grade + metadata for the composite score."""
    score = max(0, min(100, int(score)))
    selected = RATING_SCALE[0]
    for code, minimum, label in RATING_SCALE:
        if score >= minimum:
            selected = (code, minimum, label)

    code, minimum, label = selected
    idx = RATING_ORDER.index(code)
    progress = round((idx / (len(RATING_ORDER) - 1)) * 100)
    tone = RATING_TONES[code]

    return {
        "code": code,
        "label": label,
        "score": score,
        "index": idx,
        "progress": progress,
        "scale": RATING_ORDER,
        "is_top": code == "AA",
        "is_low": code == "DD",
        "metric": "CVI",
        "metric_name": "Centropic Visibility Index",
        "band": tone["band"],
        "tone": tone["tone"],
    }


def compute_rating(
    aio_score: int | None,
    geo_score: int | None,
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    score = composite_score(aio_score, geo_score, findings)
    return grade_from_score(score)
