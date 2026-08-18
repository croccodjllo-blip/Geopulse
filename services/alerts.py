"""Outbound alerts: email + signed webhook on monitoring findings."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import requests

from services.mailer import mail_configured, send_email
from services.ssrf import UnsafeURLError, assert_public_http_url, safe_post

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
    """POST firmato verso URL pubblico HTTPS (SSRF-safe, DNS-pinned)."""
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
        "User-Agent": "Centropic-Webhook/1.0",
        "X-Centropic-Event": str(payload.get("event") or "analysis.alert"),
        # Legacy alias for existing customer integrations
        "X-GeoPulse-Event": str(payload.get("event") or "analysis.alert"),
    }
    if secret:
        sig = sign_payload(secret, body)
        headers["X-Centropic-Signature"] = sig
        headers["X-GeoPulse-Signature"] = sig
    try:
        sess = requests.Session()
        res = safe_post(
            sess,
            safe_url,
            data=body,
            timeout=timeout,
            max_redirects=0,
            headers=headers,
        )
    except UnsafeURLError as exc:
        logger.warning("alert webhook blocked (ssrf post): %s", exc)
        return {"ok": False, "error": f"ssrf_blocked:{exc}"[:160]}
    except requests.RequestException as exc:
        logger.warning("alert webhook transport error: %s", exc)
        return {"ok": False, "error": f"transport:{exc}"[:160]}
    return {
        "ok": res.status_code < 300,
        "status": res.status_code,
        "body": (res.text or "")[:200],
    }


def _user_may_dispatch_alerts(user: Any) -> bool:
    """Entitlement gate — settings may still hold stale Free-after-downgrade flags."""
    try:
        if getattr(user, "is_admin", False):
            return True
        if bool(getattr(user, "is_pro", False)):
            return True
        plan = (getattr(user, "plan", None) or "").lower()
        return plan in {"plus", "pro", "business", "admin"}
    except Exception:
        logger.exception("alert entitlement check failed — fail closed")
        return False


def dispatch_alerts(
    *,
    user: Any,
    site: Any,
    findings: list[dict[str, Any]],
    rating: dict[str, Any] | None = None,
    base_url: str = "https://centropic.ai",
    db_session: Any | None = None,
    AlertDelivery: Any | None = None,
) -> dict[str, Any]:
    """Invia email/webhook se l’utente ha abilitato gli alert."""
    alerts = _alert_findings(findings)
    result: dict[str, Any] = {"alerts": len(alerts), "email": None, "webhook": None}
    if not alerts:
        return result
    if not _user_may_dispatch_alerts(user):
        result["skipped"] = "entitlement"
        return result

    email_on = bool(getattr(user, "alert_email_enabled", True))
    webhook_url = (getattr(user, "webhook_url", None) or "").strip()
    from services.webhook_crypto import (
        reveal_webhook_secret,
        upgrade_webhook_secret_if_plaintext,
    )

    # Lazy-upgrade legacy plaintext secrets when we have a session.
    upgrade_webhook_secret_if_plaintext(user, db_session)
    webhook_secret = reveal_webhook_secret(getattr(user, "webhook_secret", None))

    lines = [
        f"Centropic alert — {getattr(site, 'domain', '') or getattr(site, 'url', '')}",
        f"Rating: {(rating or {}).get('code', 'n/d')}",
        "",
    ]
    for f in alerts[:12]:
        lines.append(f"- [{f.get('severity')}] {f.get('title')}: {f.get('detail')}")
    lines.append("")
    lines.append(f"Dashboard: {base_url.rstrip('/')}/dashboard")
    text = "\n".join(lines)
    title_summary = (alerts[0].get("title") if alerts else "Alert") or "Alert"
    site_url = getattr(site, "url", None) or getattr(site, "domain", None)

    def _log_delivery(channel: str, ok: bool, detail: str | None = None) -> None:
        if db_session is None or AlertDelivery is None:
            return
        try:
            row = AlertDelivery(
                user_id=getattr(user, "id", None),
                site_url=(str(site_url)[:500] if site_url else None),
                channel=channel[:40],
                title=str(title_summary)[:300],
                body=text[:8000],
                ok=bool(ok),
                detail=(detail or "")[:500] or None,
            )
            db_session.add(row)
            db_session.commit()
        except Exception:
            logger.exception("alert delivery log failed")
            try:
                db_session.rollback()
            except Exception:
                pass

    if email_on and mail_configured():
        try:
            send_email(
                to_email=user.email,
                subject=f"[Centropic] Alert su {getattr(site, 'domain', 'sito')}",
                text_body=text,
            )
            result["email"] = {"ok": True}
            _log_delivery("email", True)
        except Exception as exc:
            logger.exception("alert email failed")
            result["email"] = {"ok": False, "error": str(exc)[:160]}
            _log_delivery("email", False, str(exc)[:160])

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
            wh = result["webhook"] or {}
            _log_delivery(
                "webhook",
                bool(wh.get("ok")),
                str(wh.get("error") or wh.get("status") or "")[:160],
            )
        except Exception as exc:
            logger.exception("alert webhook failed")
            result["webhook"] = {"ok": False, "error": str(exc)[:160]}
            _log_delivery("webhook", False, str(exc)[:160])

    return result
