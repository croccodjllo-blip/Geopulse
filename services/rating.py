"""Indice di risultato GeoPulse: da DDD (peggiore) ad AAA (migliore)."""

from __future__ import annotations

from typing import Any

# Scala ordinata dal peggiore al migliore
RATING_SCALE: list[tuple[str, int, str]] = [
    ("DDD", 0, "Critico — segnali AIO/GEO assenti o bloccati"),
    ("DD", 15, "Molto debole — interventi urgenti"),
    ("D", 25, "Debole — base tecnica insufficiente"),
    ("CCC", 35, "Insufficiente — mancano asset chiave"),
    ("CC", 45, "Scarso — ottimizzazione ancora iniziale"),
    ("C", 55, "Mediocre — alcuni segnali, molti gap"),
    ("B", 63, "Discreto — struttura utile ma incompleta"),
    ("BB", 71, "Buono — buona base, margini chiari"),
    ("BBB", 78, "Solido — pronto per rafforzamenti mirati"),
    ("A", 85, "Ottimo — segnali AIO/GEO ben impostati"),
    ("AA", 92, "Eccellente — quasi completo"),
    ("AAA", 97, "Top — sito molto citabile dalle IA"),
]

RATING_ORDER = [code for code, _, _ in RATING_SCALE]


def composite_score(
    aio_score: int | None,
    geo_score: int | None,
    findings: list[dict[str, Any]] | None = None,
) -> int:
    """Media AIO/GEO con penalità sui findings critical/warn."""
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
    """Restituisce l’indice lettera e metadati per lo score composito."""
    score = max(0, min(100, int(score)))
    selected = RATING_SCALE[0]
    for code, minimum, label in RATING_SCALE:
        if score >= minimum:
            selected = (code, minimum, label)

    code, minimum, label = selected
    idx = RATING_ORDER.index(code)
    # 0 = DDD, 1 = AAA (progresso sulla scala)
    progress = round((idx / (len(RATING_ORDER) - 1)) * 100)

    return {
        "code": code,
        "label": label,
        "score": score,
        "index": idx,
        "progress": progress,
        "scale": RATING_ORDER,
        "is_top": code == "AAA",
        "is_low": code in {"DDD", "DD", "D"},
    }


def compute_rating(
    aio_score: int | None,
    geo_score: int | None,
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    score = composite_score(aio_score, geo_score, findings)
    return grade_from_score(score)
