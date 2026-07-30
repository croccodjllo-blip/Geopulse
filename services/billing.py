"""Stripe Billing helpers for GeoPulse Plus (Checkout + Portal + webhooks)."""

from __future__ import annotations

import logging
import os
import secrets
import string
from typing import Any

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
STRIPE_WEBHOOK_SECRET = (os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()
STRIPE_PRICE_PLUS = (os.getenv("STRIPE_PRICE_PLUS_MONTHLY") or "").strip()
STRIPE_PUBLISHABLE_KEY = (os.getenv("STRIPE_PUBLISHABLE_KEY") or "").strip()


def stripe_enabled() -> bool:
    return bool(STRIPE_SECRET_KEY and STRIPE_PRICE_PLUS)


def payments_provider() -> str:
    """Active checkout provider: paddle | stripe | none.

    Paddle is preferred when configured (merchant-of-record for EU SaaS).
    Ready if Plus and/or credit top-up prices are configured.
    """
    try:
        from services.paddle_billing import paddle_enabled, paddle_topups_enabled

        if paddle_enabled() or paddle_topups_enabled():
            return "paddle"
    except Exception:
        logger.debug("paddle_enabled check failed", exc_info=True)
    if stripe_enabled():
        return "stripe"
    return "none"


def payments_enabled() -> bool:
    return payments_provider() != "none"


def _client():
    if not STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY non configurata")
    import stripe

    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


def _integration_id() -> str:
    suffix = "".join(secrets.choice(string.ascii_lowercase) for _ in range(8))
    return f"geopulse_plus_{suffix}"


def ensure_customer(*, user_id: int, email: str, name: str, customer_id: str | None) -> str:
    stripe = _client()
    if customer_id:
        return customer_id
    customer = stripe.Customer.create(
        email=email,
        name=name or email,
        metadata={"geopulse_user_id": str(user_id)},
    )
    return customer["id"]


def create_checkout_session(
    *,
    user_id: int,
    email: str,
    name: str,
    customer_id: str | None,
    success_url: str,
    cancel_url: str,
) -> dict[str, Any]:
    stripe = _client()
    if not STRIPE_PRICE_PLUS:
        raise RuntimeError("STRIPE_PRICE_PLUS_MONTHLY non configurata")
    cid = ensure_customer(
        user_id=user_id, email=email, name=name, customer_id=customer_id
    )
    params: dict[str, Any] = {
        "mode": "subscription",
        "customer": cid,
        "line_items": [{"price": STRIPE_PRICE_PLUS, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(user_id),
        "metadata": {"geopulse_user_id": str(user_id)},
        "subscription_data": {"metadata": {"geopulse_user_id": str(user_id)}},
        "allow_promotion_codes": True,
    }
    # API 2026-03-25+ optional; ignore if SDK rejects
    try:
        params["integration_identifier"] = _integration_id()
        session = stripe.checkout.Session.create(**params)
    except TypeError:
        params.pop("integration_identifier", None)
        session = stripe.checkout.Session.create(**params)
    except Exception:
        params.pop("integration_identifier", None)
        session = stripe.checkout.Session.create(**params)
    return {"id": session["id"], "url": session["url"], "customer_id": cid}


def create_portal_session(*, customer_id: str, return_url: str) -> str:
    stripe = _client()
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session["url"]


def construct_event(
    payload: bytes,
    sig_header: str,
    *,
    webhook_secret: str | None = None,
):
    """Verify Stripe webhook signature.

    Use ``webhook_secret`` for dedicated endpoints (e.g. credit top-up);
    otherwise fall back to ``STRIPE_WEBHOOK_SECRET``.
    """
    stripe = _client()
    secret = (webhook_secret or STRIPE_WEBHOOK_SECRET or "").strip()
    if not secret:
        raise RuntimeError("Stripe webhook secret non configurata")
    return stripe.Webhook.construct_event(payload, sig_header, secret)


def plan_from_subscription_status(status: str | None) -> str:
    status = (status or "").lower()
    if status in {"active", "trialing"}:
        return "plus"
    return "free"
