"""Edge hit telemetry for hosted signals (/e/<token>/...)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.edge_signals import AI_CRAWLER_USER_AGENTS, is_ai_crawler


def classify_crawler(user_agent: str | None) -> str:
    ua = user_agent or ""
    lower = ua.lower()
    for bot in AI_CRAWLER_USER_AGENTS:
        token = (bot.get("ua") or "").lower()
        if token and token in lower:
            return str(bot.get("name") or token)
    if is_ai_crawler(ua):
        return "ai-other"
    if not ua.strip():
        return "unknown"
    return "browser"


def record_edge_hit(
    db_session: Any,
    *,
    EdgeHit: Any,
    site_id: int | None,
    token: str,
    path: str,
    user_agent: str | None,
    ip_hash: str | None = None,
) -> Any:
    row = EdgeHit(
        site_id=site_id,
        token=(token or "")[:64],
        path=(path or "")[:120],
        crawler=classify_crawler(user_agent)[:80],
        user_agent=(user_agent or "")[:300],
        ip_hash=(ip_hash or "")[:64] or None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return row


def top_crawlers_for_site(
    EdgeHit: Any,
    *,
    site_id: int,
    limit: int = 8,
) -> list[dict[str, Any]]:
    rows = (
        EdgeHit.query.filter_by(site_id=site_id)
        .order_by(EdgeHit.created_at.desc())
        .limit(500)
        .all()
    )
    counts: dict[str, int] = {}
    for r in rows:
        key = getattr(r, "crawler", None) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:limit]
    return [{"crawler": k, "hits": v} for k, v in ranked]
