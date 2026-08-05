"""Payment provider facade — Paddle only (merchant of record).

Historical note: DB columns ``stripe_*`` / ``stripe_payment_intent`` still store
Paddle customer/subscription IDs and idempotency keys (`paddle:…`) for
backward compatibility. New code must not call Stripe APIs.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def stripe_enabled() -> bool:
    """Always False — Stripe checkout/webhooks removed."""
    return False


def payments_provider() -> str:
    """Active checkout provider: paddle | none."""
    try:
        from services.paddle_billing import paddle_enabled, paddle_topups_enabled

        if paddle_enabled() or paddle_topups_enabled():
            return "paddle"
    except Exception:
        logger.debug("paddle_enabled check failed", exc_info=True)
    return "none"


def payments_enabled() -> bool:
    return payments_provider() != "none"
