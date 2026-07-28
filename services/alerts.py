"""Outbound alerts: email + signed webhook on monitoring findings."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import requests

from services.mailer import mail_configured, send_email
from services.ssrf import UnsafeURLError, assert_public_http_url

logger = logging.getLogger(__name__)

WEBHOOK_MAX_BODY = 64_000


def _alert_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for f in findings or []:
        title = str(f.get("title") or "")
        sev = str(f.get("severity") or "").lower()
        if sev in {"critical", "warn"} and (
            title.lower().startswith("alert:")
            or "regressione" in title.lower()
            or "sparito" in title.lower()
            or "publish verify" in title.lower()
            or "pack non pubblicato" in title.lower()
        ):
            out.append(f)
        elif sev == "critical" and f.get("category") == "diff":
            out.append(f)
    return out


def sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def deliver_webhook(
    *,
    url: str,
    secret: str,
    payload: dict[str, Any],
    timeout: int = 12,
) -> dict[str, Any]:
    """POST firmato verso URL pubblico HTTPS (SSRF-safe)."""
    try:
        safe_url = assert_public_http_url(url, resolve=True)
    except UnsafeURLError as exc:
        logger.warning("alert webhook blocked (ssrf): %s", exc)
        return {"ok": False, "error": f"ssrf_blocked:{exc}"[:160]}

    # Solo HTTPS in produzione alert outbound (mitiga MITM su endpoint clienti).
    if not safe_url.startswith("https://"):
        return {"ok": False, "error": "webhook_https_required"}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(body) > WEBHOOK_MAX_BODY:
        body = body[:WEBHOOK_MAX_BODY]
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "GeoPulse-Webhook/1.0",
        "X-GeoPulse-Event": str(payload.get("event") or "analysis.alert"),
    }
    if secret:
        headers["X-GeoPulse-Signature"] = sign_payload(secret, body)
    res = requests.post(
        safe_url,
        data=body,
        headers=headers,
        timeout=timeout,
        allow_redirects=False,
    )
    return {
        "ok": res.status_code < 300,
        "status": res.status_code,
        "body": (res.text or "")[:200],
    }


def dispatch_alerts(
    *,
    user: Any,
    site: Any,
    findings: list[dict[str, Any]],
    rating: dict[str, Any] | None = None,
    base_url: str = "https://geopulse.it",
) -> dict[str, Any]:
    """Invia email/webhook se l’utente ha abilitato gli alert."""
    alerts = _alert_findings(findings)
    result: dict[str, Any] = {"alerts": len(alerts), "email": None, "webhook": None}
    if not alerts:
        return result

    email_on = bool(getattr(user, "alert_email_enabled", True))
    webhook_url = (getattr(user, "webhook_url", None) or "").strip()
    webhook_secret = (getattr(user, "webhook_secret", None) or "").strip()

    lines = [
        f"GeoPulse alert — {getattr(site, 'domain', '') or getattr(site, 'url', '')}",
        f"Rating: {(rating or {}).get('code', 'n/d')}",
        "",
    ]
    for f in alerts[:12]:
        lines.append(f"- [{f.get('severity')}] {f.get('title')}: {f.get('detail')}")
    lines.append("")
    lines.append(f"Dashboard: {base_url.rstrip('/')}/dashboard")
    text = "\n".join(lines)

    if email_on and mail_configured():
        try:
            send_email(
                to_email=user.email,
                subject=f"[GeoPulse] Alert su {getattr(site, 'domain', 'sito')}",
                text_body=text,
            )
            result["email"] = {"ok": True}
        except Exception as exc:
            logger.exception("alert email failed")
            result["email"] = {"ok": False, "error": str(exc)[:160]}

    if webhook_url.startswith("http"):
        payload = {
            "event": "analysis.alert",
            "site": {
                "id": getattr(site, "id", None),
                "url": getattr(site, "url", None),
                "domain": getattr(site, "domain", None),
            },
            "rating": rating or {},
            "alerts": alerts[:20],
        }
        try:
            result["webhook"] = deliver_webhook(
                url=webhook_url, secret=webhook_secret, payload=payload
            )
        except Exception as exc:
            logger.exception("alert webhook failed")
            result["webhook"] = {"ok": False, "error": str(exc)[:160]}

    return result
