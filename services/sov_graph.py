"""Measurement graph: SoV snapshots over time (per site / run)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def extract_sov_snapshot(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """Pull measured SoV payload from an analysis result dict."""
    if not isinstance(result, dict):
        return None
    signals = result.get("signals") or {}
    if not isinstance(signals, dict):
        return None
    sov = signals.get("sov_measured") or result.get("sov_measured")
    if not isinstance(sov, dict):
        return None
    if not sov.get("available") and sov.get("evidence") not in {"measured", "mixed"}:
        # Still store if engines list present (partial measured)
        engines = sov.get("engines") or []
        if not any(
            isinstance(e, dict) and e.get("evidence") == "measured" for e in engines
        ):
            return None
    engines = []
    for e in sov.get("engines") or []:
        if not isinstance(e, dict):
            continue
        engines.append(
            {
                "id": e.get("id"),
                "label": e.get("label"),
                "mention_rate": e.get("mention_rate"),
                "evidence": e.get("evidence"),
                "model": e.get("model"),
            }
        )
    return {
        "brand_mention_rate": sov.get("brand_mention_rate"),
        "evidence": sov.get("evidence") or "measured",
        "engines": engines,
        "label": sov.get("label"),
    }


def persist_sov_snapshot(
    db_session: Any,
    *,
    SovSnapshot: Any,
    site_id: int,
    user_id: int,
    run_id: int | None,
    snapshot: dict[str, Any],
    source: str = "analyze",
) -> Any | None:
    if not snapshot:
        return None
    row = SovSnapshot(
        site_id=site_id,
        user_id=user_id,
        run_id=run_id,
        brand_mention_rate=snapshot.get("brand_mention_rate"),
        evidence=str(snapshot.get("evidence") or "measured")[:40],
        engines_json=json.dumps(snapshot.get("engines") or [], ensure_ascii=False),
        source=str(source or "analyze")[:40],
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    return row


def list_sov_snapshots(
    SovSnapshot: Any,
    *,
    site_id: int,
    user_id: int,
    limit: int = 30,
) -> list[Any]:
    return (
        SovSnapshot.query.filter_by(site_id=site_id, user_id=user_id)
        .order_by(SovSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )


def sov_series_for_chart(rows: list[Any]) -> list[dict[str, Any]]:
    """Oldest→newest points for sparkline / SVG."""
    points: list[dict[str, Any]] = []
    for row in reversed(list(rows or [])):
        created = getattr(row, "created_at", None)
        points.append(
            {
                "t": created.isoformat() if created else "",
                "rate": getattr(row, "brand_mention_rate", None),
                "evidence": getattr(row, "evidence", None),
            }
        )
    return points


def sov_delta_findings(
    *,
    current: dict[str, Any] | None,
    previous_rate: float | None,
    threshold_drop: float = 15.0,
) -> list[dict[str, str]]:
    """Alert-style findings when measured brand SoV drops."""
    if not current:
        return []
    rate = current.get("brand_mention_rate")
    if rate is None or previous_rate is None:
        return []
    try:
        cur = float(rate)
        prev = float(previous_rate)
    except (TypeError, ValueError):
        return []
    drop = prev - cur
    if drop < threshold_drop:
        return []
    return [
        {
            "category": "geo",
            "severity": "critical" if drop >= 25 else "warn",
            "title": "Alert: SoV measured in calo",
            "detail": (
                f"Brand mention rate mediato da {prev:.0f}% a {cur:.0f}% "
                f"(Δ −{drop:.0f} pt). Controlla artifact e prompt bank."
            ),
            "evidence": "measured",
        }
    ]


def previous_brand_rate(SovSnapshot: Any, *, site_id: int, user_id: int) -> float | None:
    row = (
        SovSnapshot.query.filter_by(site_id=site_id, user_id=user_id)
        .order_by(SovSnapshot.created_at.desc())
        .first()
    )
    if row is None or row.brand_mention_rate is None:
        return None
    try:
        return float(row.brand_mention_rate)
    except (TypeError, ValueError):
        return None
