"""Paddle Billing helpers for Centropic (Plus subscription + credit top-ups)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

PADDLE_API_KEY = (os.getenv("PADDLE_API_KEY") or "").strip()
PADDLE_CLIENT_TOKEN = (os.getenv("PADDLE_CLIENT_TOKEN") or "").strip()
PADDLE_WEBHOOK_SECRET = (os.getenv("PADDLE_WEBHOOK_SECRET") or "").strip()
PADDLE_ENV = (os.getenv("PADDLE_ENV") or "sandbox").strip().lower()
PADDLE_PRICE_PLUS = (os.getenv("PADDLE_PRICE_PLUS_MONTHLY") or "").strip()
PADDLE_PRICE_PLUS_YEARLY = (os.getenv("PADDLE_PRICE_PLUS_YEARLY") or "").strip()
PADDLE_PRICE_BUSINESS = (os.getenv("PADDLE_PRICE_BUSINESS_MONTHLY") or "").strip()
PADDLE_PRICE_BUSINESS_YEARLY = (os.getenv("PADDLE_PRICE_BUSINESS_YEARLY") or "").strip()

# Optional per-package catalog prices (EUR cents payment → pri_…)
# Packs: €10→100 token, €20→200 token, €50→600 token (1 token = €0.10).
_TOPUP_ENV = {
    1000: "PADDLE_PRICE_TOPUP_1000",
    2000: "PADDLE_PRICE_TOPUP_2000",
    5000: "PADDLE_PRICE_TOPUP_5000",
}


def paddle_environment() -> str:
    return "sandbox" if PADDLE_ENV in {"sandbox", "test", "sandbox-api"} else "production"


def assert_paddle_env_matches_site(
    *,
    public_site_url: str,
    flask_debug: bool = False,
    allow_sandbox_on_prod: bool | None = None,
) -> None:
    """Fail-fast when production public URL would talk to Paddle sandbox.

    Override with ALLOW_PADDLE_SANDBOX_ON_PROD=1 for emergency staging.
    """
    if allow_sandbox_on_prod is None:
        allow_sandbox_on_prod = (os.getenv("ALLOW_PADDLE_SANDBOX_ON_PROD") or "").strip() in {
            "1",
            "true",
            "yes",
        }
    if flask_debug or allow_sandbox_on_prod:
        return
    if paddle_environment() != "sandbox":
        return
    host = (public_site_url or "").strip().lower()
    if "centropic.ai" in host and "localhost" not in host and "127.0.0.1" not in host:
        raise RuntimeError(
            "PADDLE_ENV=sandbox with PUBLIC_SITE_URL pointing at production "
            f"({public_site_url}). Set PADDLE_ENV=production or "
            "ALLOW_PADDLE_SANDBOX_ON_PROD=1 for intentional staging."
        )


def paddle_api_base() -> str:
    if paddle_environment() == "sandbox":
        return "https://sandbox-api.paddle.com"
    return "https://api.paddle.com"


def paddle_enabled() -> bool:
    """Any subscription checkout ready: Plus and/or Business + auth."""
    has_price = bool(PADDLE_PRICE_PLUS or PADDLE_PRICE_BUSINESS)
    return bool(has_price and (PADDLE_CLIENT_TOKEN or PADDLE_API_KEY))


def paddle_plus_enabled() -> bool:
    return bool(PADDLE_PRICE_PLUS and (PADDLE_CLIENT_TOKEN or PADDLE_API_KEY))


def paddle_business_enabled() -> bool:
    return bool(PADDLE_PRICE_BUSINESS and (PADDLE_CLIENT_TOKEN or PADDLE_API_KEY))


def paddle_overlay_ready() -> bool:
    """Paddle.js overlay usable for subscriptions and/or configured top-ups."""
    if not PADDLE_CLIENT_TOKEN:
        return False
    return bool(PADDLE_PRICE_PLUS or PADDLE_PRICE_BUSINESS or topup_price_map())


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
    overlay = paddle_overlay_ready()
    return {
        "enabled": paddle_enabled() or paddle_topups_enabled(),
        "overlay": overlay,
        "plusReady": paddle_plus_enabled(),
        "businessReady": paddle_business_enabled(),
        "environment": paddle_environment(),
        "clientToken": PADDLE_CLIENT_TOKEN if overlay else "",
        "pricePlus": PADDLE_PRICE_PLUS,
        "pricePlusYearly": PADDLE_PRICE_PLUS_YEARLY,
        "priceBusiness": PADDLE_PRICE_BUSINESS,
        "priceBusinessYearly": PADDLE_PRICE_BUSINESS_YEARLY,
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
        logger.warning(
            "Paddle create_transaction failed: HTTP %s", res.status_code
        )
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
    interval: str = "month",
) -> dict[str, Any]:
    yearly = (interval or "").lower() in {"year", "yearly", "annual", "annuale"}
    price_id = (
        (os.getenv("PADDLE_PRICE_PLUS_YEARLY") or PADDLE_PRICE_PLUS_YEARLY or "").strip()
        if yearly
        else (os.getenv("PADDLE_PRICE_PLUS_MONTHLY") or PADDLE_PRICE_PLUS or "").strip()
    )
    if not price_id:
        raise RuntimeError(
            "PADDLE_PRICE_PLUS_YEARLY non configurata"
            if yearly
            else "PADDLE_PRICE_PLUS_MONTHLY non configurata"
        )
    return create_transaction(
        price_id=price_id,
        user_id=user_id,
        email=email,
        custom_data={"product": "plus", "interval": "year" if yearly else "month"},
        success_url=success_url,
        customer_id=customer_id,
    )


def create_business_checkout(
    *,
    user_id: int,
    email: str,
    customer_id: str | None = None,
    success_url: str | None = None,
    interval: str = "month",
) -> dict[str, Any]:
    yearly = (interval or "").lower() in {"year", "yearly", "annual", "annuale"}
    price_id = (
        (
            os.getenv("PADDLE_PRICE_BUSINESS_YEARLY")
            or PADDLE_PRICE_BUSINESS_YEARLY
            or ""
        ).strip()
        if yearly
        else (
            os.getenv("PADDLE_PRICE_BUSINESS_MONTHLY") or PADDLE_PRICE_BUSINESS or ""
        ).strip()
    )
    if not price_id:
        raise RuntimeError(
            "PADDLE_PRICE_BUSINESS_YEARLY non configurata"
            if yearly
            else "PADDLE_PRICE_BUSINESS_MONTHLY non configurata"
        )
    return create_transaction(
        price_id=price_id,
        user_id=user_id,
        email=email,
        custom_data={"product": "business", "interval": "year" if yearly else "month"},
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
    """Verify Paddle-Signature: ``ts=…;h1=…`` over ``{ts}:{raw_body}``.

    Supports multiple ``h1`` values (secret rotation) and multiple secrets
    (comma-separated ``PADDLE_WEBHOOK_SECRET``).
    """
    secrets = _webhook_secrets(secret)
    if not secrets or not signature_header:
        logger.warning(
            "Paddle webhook verify fail: %s",
            "missing_secret" if not secrets else "missing_signature_header",
        )
        return False

    if isinstance(raw_body, bytes):
        body_bytes = raw_body
    else:
        body_bytes = raw_body.encode("utf-8")

    ts: str | None = None
    h1_values: list[str] = []
    for element in signature_header.split(";"):
        element = element.strip()
        if "=" not in element:
            continue
        key, value = element.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "ts":
            ts = value
        elif key == "h1" and value:
            h1_values.append(value)
    if not ts or not h1_values:
        logger.warning("Paddle webhook verify fail: malformed_signature_header")
        return False
    try:
        age = abs(int(time.time()) - int(ts))
    except ValueError:
        logger.warning("Paddle webhook verify fail: bad_timestamp")
        return False
    if age > max_age_seconds:
        logger.warning("Paddle webhook timestamp too old (%ss)", age)
        return False

    signed = f"{ts}:".encode("utf-8") + body_bytes
    for sec in secrets:
        digest = hmac.new(sec.encode("utf-8"), signed, hashlib.sha256).hexdigest()
        for h1 in h1_values:
            if hmac.compare_digest(digest, h1):
                return True
    logger.warning(
        "Paddle webhook verify fail: signature_mismatch (secrets=%s h1=%s age=%ss)",
        len(secrets),
        len(h1_values),
        age,
    )
    return False


def _webhook_secrets(explicit: str | None = None) -> list[str]:
    """Collect webhook secrets from arg or env (comma-separated allowed)."""
    raw = (explicit if explicit is not None else os.getenv("PADDLE_WEBHOOK_SECRET") or "")
    raw = str(raw).strip()
    if not raw:
        # Fall back to module-level for tests that monkeypatch the constant.
        raw = (PADDLE_WEBHOOK_SECRET or "").strip()
    out: list[str] = []
    for part in raw.split(","):
        s = part.strip().strip('"').strip("'")
        if s and s not in out:
            out.append(s)
    return out


def parse_webhook_event(raw_body: bytes | str) -> dict[str, Any]:
    if isinstance(raw_body, bytes):
        raw_body = raw_body.decode("utf-8")
    data = json.loads(raw_body)
    if not isinstance(data, dict):
        raise ValueError("invalid paddle webhook payload")
    return data


def plan_from_paddle_subscription_status(
    status: str | None,
    *,
    past_due_at: datetime | None = None,
    now: datetime | None = None,
    past_due_grace_days: int = 3,
    paid_plan: str = "plus",
) -> str:
    """Map Paddle subscription status → Centropic plan.

    ``past_due`` keeps the paid plan only within ``past_due_grace_days`` from
    ``past_due_at`` (webhook event time). Without a timestamp, past_due
    does not grant access (fail closed).

    ``paid_plan`` should be ``plus`` or ``business`` when the subscription
    price is known.
    """
    target = (paid_plan or "plus").lower()
    if target not in {"plus", "business"}:
        target = "plus"
    status = (status or "").lower()
    if status in {"active", "trialing"}:
        return target
    if status == "past_due":
        if past_due_at is None:
            return "free"
        ref = now or datetime.now(timezone.utc)
        started = past_due_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        grace = timedelta(days=max(0, int(past_due_grace_days)))
        if ref <= started + grace:
            return target
        return "free"
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


def transaction_price_ids(data: dict[str, Any]) -> list[str]:
    """Collect price_id values from a Paddle transaction payload."""
    out: list[str] = []
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        price = item.get("price") if isinstance(item.get("price"), dict) else {}
        pid = (
            item.get("price_id")
            or (price or {}).get("id")
            or (price or {}).get("price_id")
        )
        if pid:
            text = str(pid).strip()
            if text and text not in out:
                out.append(text)
    return out


def plus_price_id() -> str:
    """Configured Plus monthly price id (re-read env for tests / runtime)."""
    return (os.getenv("PADDLE_PRICE_PLUS_MONTHLY") or PADDLE_PRICE_PLUS or "").strip()


def plus_yearly_price_id() -> str:
    return (
        os.getenv("PADDLE_PRICE_PLUS_YEARLY") or PADDLE_PRICE_PLUS_YEARLY or ""
    ).strip()


def business_price_id() -> str:
    return (
        os.getenv("PADDLE_PRICE_BUSINESS_MONTHLY") or PADDLE_PRICE_BUSINESS or ""
    ).strip()


def business_yearly_price_id() -> str:
    return (
        os.getenv("PADDLE_PRICE_BUSINESS_YEARLY") or PADDLE_PRICE_BUSINESS_YEARLY or ""
    ).strip()


def paid_plan_from_price_ids(price_ids: list[str] | set[str]) -> str | None:
    """Return ``business`` / ``plus`` if settled prices match catalog, else None."""
    settled = {str(p).strip() for p in price_ids if p}
    biz = {business_price_id(), business_yearly_price_id()} - {""}
    plus = {plus_price_id(), plus_yearly_price_id()} - {""}
    if biz & settled:
        return "business"
    if plus & settled:
        return "plus"
    return None


def transaction_grants_plus(data: dict[str, Any]) -> bool:
    """Grant Plus only when settled line items include a Plus price.

    Never trust client ``custom_data.product`` — overlay checkout can set it.
    """
    return paid_plan_from_price_ids(transaction_price_ids(data)) == "plus"


def transaction_grants_business(data: dict[str, Any]) -> bool:
    """Grant Business only when settled line items include a Business price."""
    return paid_plan_from_price_ids(transaction_price_ids(data)) == "business"


def subscription_paid_plan(
    data: dict[str, Any], *, current_plan: str | None = None
) -> str | None:
    """Paid plan for an active subscription payload.

    Fail closed: never invent ``plus`` when price IDs are missing/unknown.
    Falls back to ``current_plan`` only when it is already a paid plan
    (renewal webhooks that omit item price ids).
    """
    from_prices = paid_plan_from_price_ids(transaction_price_ids(data))
    if from_prices:
        return from_prices
    # Some subscription payloads nest price under items differently — already
    # covered by transaction_price_ids; if still empty, keep current paid plan.
    cur = (current_plan or "").lower()
    if cur == "business":
        return "business"
    if cur in {"plus", "pro"}:
        return "plus"
    return None


def topup_payment_cents_for_transaction(data: dict[str, Any]) -> int | None:
    """Map settled price_id → payment EUR cents via server catalog.

    Ignore client ``custom_data`` — overlay checkout can set it.
    """
    inverse = {pid: cents for cents, pid in topup_price_map().items()}
    if not inverse:
        return None
    for pid in transaction_price_ids(data):
        if pid in inverse:
            return int(inverse[pid])
    return None


def topup_cents_for_transaction(data: dict[str, Any]) -> int | None:
    """Backward-compatible alias: payment cents for the settled top-up price."""
    return topup_payment_cents_for_transaction(data)


def transaction_gross_cents(data: dict[str, Any]) -> int | None:
    """Best-effort paid amount in minor units (EUR cents).

    Uses Paddle totals only — never falls back to client custom_data.
    """
    details = data.get("details") or {}
    totals = details.get("totals") or {}
    for key in ("grand_total", "total", "subtotal"):
        raw = totals.get(key)
        if raw is None:
            continue
        try:
            if isinstance(raw, (int, float)):
                return int(round(float(raw)))
            text = str(raw).strip()
            if "." in text:
                return int(round(float(text) * 100))
            return int(text)
        except (TypeError, ValueError):
            continue
    return None
