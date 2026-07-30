"""Paddle Billing helpers for Centropic (Plus subscription + credit top-ups)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

PADDLE_API_KEY = (os.getenv("PADDLE_API_KEY") or "").strip()
PADDLE_CLIENT_TOKEN = (os.getenv("PADDLE_CLIENT_TOKEN") or "").strip()
PADDLE_WEBHOOK_SECRET = (os.getenv("PADDLE_WEBHOOK_SECRET") or "").strip()
PADDLE_ENV = (os.getenv("PADDLE_ENV") or "sandbox").strip().lower()
PADDLE_PRICE_PLUS = (os.getenv("PADDLE_PRICE_PLUS_MONTHLY") or "").strip()

# Optional per-package catalog prices (EUR cents → pri_…)
_TOPUP_ENV = {
    100: "PADDLE_PRICE_TOPUP_100",
    500: "PADDLE_PRICE_TOPUP_500",
    1000: "PADDLE_PRICE_TOPUP_1000",
    5000: "PADDLE_PRICE_TOPUP_5000",
    10000: "PADDLE_PRICE_TOPUP_10000",
}


def paddle_environment() -> str:
    return "sandbox" if PADDLE_ENV in {"sandbox", "test", "sandbox-api"} else "production"


def paddle_api_base() -> str:
    if paddle_environment() == "sandbox":
        return "https://sandbox-api.paddle.com"
    return "https://api.paddle.com"


def paddle_enabled() -> bool:
    """Plus checkout ready: price + (client token for overlay OR API key for hosted)."""
    return bool(PADDLE_PRICE_PLUS and (PADDLE_CLIENT_TOKEN or PADDLE_API_KEY))


def paddle_overlay_ready() -> bool:
    return bool(PADDLE_CLIENT_TOKEN and PADDLE_PRICE_PLUS)


def paddle_topup_price_id(amount_cents: int) -> str | None:
    env_name = _TOPUP_ENV.get(int(amount_cents))
    if not env_name:
        return None
    return (os.getenv(env_name) or "").strip() or None


def paddle_topups_enabled() -> bool:
    if not (PADDLE_CLIENT_TOKEN or PADDLE_API_KEY):
        return False
    return any(paddle_topup_price_id(c) for c in _TOPUP_ENV)


def topup_price_map() -> dict[int, str]:
    out: dict[int, str] = {}
    for cents, env_name in _TOPUP_ENV.items():
        pid = (os.getenv(env_name) or "").strip()
        if pid:
            out[cents] = pid
    return out


def client_config() -> dict[str, Any]:
    """Public config for Paddle.js (safe to embed in HTML)."""
    return {
        "enabled": paddle_enabled(),
        "overlay": paddle_overlay_ready(),
        "environment": paddle_environment(),
        "clientToken": PADDLE_CLIENT_TOKEN if paddle_overlay_ready() else "",
        "pricePlus": PADDLE_PRICE_PLUS,
        "topupPrices": {str(k): v for k, v in topup_price_map().items()},
    }


def _api_headers() -> dict[str, str]:
    if not PADDLE_API_KEY:
        raise RuntimeError("PADDLE_API_KEY non configurata")
    return {
        "Authorization": f"Bearer {PADDLE_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def create_transaction(
    *,
    price_id: str,
    user_id: int,
    email: str,
    custom_data: dict[str, Any] | None = None,
    success_url: str | None = None,
    customer_id: str | None = None,
) -> dict[str, Any]:
    """Create a Paddle transaction and return checkout URL + ids."""
    payload: dict[str, Any] = {
        "items": [{"price_id": price_id, "quantity": 1}],
        "custom_data": {
            "centropic_user_id": str(user_id),
            **(custom_data or {}),
        },
    }
    if customer_id:
        payload["customer_id"] = customer_id
    else:
        payload["customer"] = {"email": email}
    if success_url:
        payload["checkout"] = {"url": success_url}

    res = requests.post(
        f"{paddle_api_base()}/transactions",
        headers=_api_headers(),
        json=payload,
        timeout=30,
    )
    if res.status_code >= 400:
        logger.warning("Paddle create_transaction failed: %s %s", res.status_code, res.text[:400])
        raise RuntimeError(f"Paddle transaction error HTTP {res.status_code}")
    body = res.json()
    data = body.get("data") or {}
    checkout = data.get("checkout") or {}
    return {
        "id": data.get("id"),
        "status": data.get("status"),
        "url": checkout.get("url"),
        "customer_id": data.get("customer_id"),
        "raw": data,
    }


def create_plus_checkout(
    *,
    user_id: int,
    email: str,
    customer_id: str | None = None,
    success_url: str | None = None,
) -> dict[str, Any]:
    if not PADDLE_PRICE_PLUS:
        raise RuntimeError("PADDLE_PRICE_PLUS_MONTHLY non configurata")
    return create_transaction(
        price_id=PADDLE_PRICE_PLUS,
        user_id=user_id,
        email=email,
        custom_data={"product": "plus"},
        success_url=success_url,
        customer_id=customer_id,
    )


def create_topup_checkout(
    *,
    user_id: int,
    email: str,
    amount_cents: int,
    customer_id: str | None = None,
    success_url: str | None = None,
) -> dict[str, Any]:
    price_id = paddle_topup_price_id(amount_cents)
    if not price_id:
        raise RuntimeError(f"Nessun price Paddle per top-up {amount_cents} cent")
    return create_transaction(
        price_id=price_id,
        user_id=user_id,
        email=email,
        custom_data={"product": "topup", "topup_cents": str(int(amount_cents))},
        success_url=success_url,
        customer_id=customer_id,
    )


def verify_webhook_signature(
    raw_body: bytes | str,
    signature_header: str,
    *,
    secret: str | None = None,
    max_age_seconds: int = 300,
) -> bool:
    """Verify Paddle-Signature: ts=…;h1=… over ``{ts}:{raw_body}``."""
    secret = (secret or PADDLE_WEBHOOK_SECRET or "").strip()
    if not secret or not signature_header:
        return False
    if isinstance(raw_body, bytes):
        body_str = raw_body.decode("utf-8")
    else:
        body_str = raw_body

    parts: dict[str, str] = {}
    for element in signature_header.split(";"):
        element = element.strip()
        if "=" not in element:
            continue
        key, value = element.split("=", 1)
        parts[key.strip()] = value.strip()
    ts = parts.get("ts")
    h1 = parts.get("h1")
    if not ts or not h1:
        return False
    try:
        age = abs(int(time.time()) - int(ts))
    except ValueError:
        return False
    if age > max_age_seconds:
        logger.warning("Paddle webhook timestamp too old (%ss)", age)
        return False

    signed = f"{ts}:{body_str}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, h1)


def parse_webhook_event(raw_body: bytes | str) -> dict[str, Any]:
    if isinstance(raw_body, bytes):
        raw_body = raw_body.decode("utf-8")
    data = json.loads(raw_body)
    if not isinstance(data, dict):
        raise ValueError("invalid paddle webhook payload")
    return data


def plan_from_paddle_subscription_status(status: str | None) -> str:
    status = (status or "").lower()
    if status in {"active", "trialing", "past_due"}:
        # past_due: keep Plus briefly while Paddle retries payment
        return "plus"
    return "free"


def extract_user_id(custom_data: Any) -> int | None:
    if not isinstance(custom_data, dict):
        return None
    raw = (
        custom_data.get("centropic_user_id")
        or custom_data.get("geopulse_user_id")
        or custom_data.get("user_id")
    )
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def transaction_is_subscription(data: dict[str, Any]) -> bool:
    """Heuristic: subscription id present or origin subscription."""
    if data.get("subscription_id"):
        return True
    origin = (data.get("origin") or "").lower()
    if origin in {"subscription_recurring", "subscription_charge"}:
        return True
    items = data.get("items") or []
    for item in items:
        price = (item or {}).get("price") or {}
        billing = price.get("billing_cycle") or {}
        if billing.get("interval"):
            return True
    return False


def transaction_gross_cents(data: dict[str, Any]) -> int | None:
    """Best-effort paid amount in minor units (EUR cents)."""
    details = data.get("details") or {}
    totals = details.get("totals") or data.get("details", {}).get("totals") or {}
    # Paddle totals are usually strings in major currency units? Actually Billing
    # API uses lowest denomination as strings for money fields in some payloads.
    for key in ("grand_total", "total", "subtotal"):
        raw = totals.get(key)
        if raw is None:
            continue
        try:
            # Prefer integer minor units when numeric string without decimal.
            if isinstance(raw, (int, float)):
                return int(round(float(raw)))
            text = str(raw).strip()
            if "." in text:
                return int(round(float(text) * 100))
            return int(text)
        except (TypeError, ValueError):
            continue
    custom = data.get("custom_data") or {}
    try:
        return int(custom.get("topup_cents")) if custom.get("topup_cents") else None
    except (TypeError, ValueError):
        return None
