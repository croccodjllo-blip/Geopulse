"""Token top-up package pricing invariants."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-token-pricing")
os.environ.setdefault("BEHIND_NGINX", "1")

from app import (  # noqa: E402
    ADMIN_TOPUP_AMOUNTS_CENTS,
    GEO_TOKEN_EUR_CENTS,
    GEO_TOKENS_PER_EURO,
    User,
    _TOPUP_PACKAGES,
    _topup_credit_cents,
    _user_can_purchase_topup,
)
from services.paddle_billing import _TOPUP_ENV
from services.token_units import PLUS_MONTHLY_TOKENS, tokens_to_cents


def test_geo_token_rate():
    assert GEO_TOKEN_EUR_CENTS == 10
    assert GEO_TOKENS_PER_EURO == 10
    assert tokens_to_cents(100) == 1000  # €10 pack → 100 token


def test_public_packages_10_20_50_with_token_grants():
    assert [p["cents"] for p in _TOPUP_PACKAGES] == [1000, 2000, 5000]
    assert [p["tokens"] for p in _TOPUP_PACKAGES] == [100, 200, 550]
    assert [p["credit_cents"] for p in _TOPUP_PACKAGES] == [1000, 2000, 5500]
    assert [p["analyses"] for p in _TOPUP_PACKAGES] == ["~40", "~80", "~230"]
    for p in _TOPUP_PACKAGES:
        assert p["cents"] == p["price_eur"] * 100
        assert p["credit_cents"] == p["tokens"] * GEO_TOKEN_EUR_CENTS
        assert _topup_credit_cents(p["cents"]) == p["credit_cents"]
    # Base rate: €10/€20 are 10 token per euro; €50 pack has light bonus.
    assert _TOPUP_PACKAGES[0]["tokens"] == 10 * GEO_TOKENS_PER_EURO
    assert _TOPUP_PACKAGES[1]["tokens"] == 20 * GEO_TOKENS_PER_EURO
    assert _TOPUP_PACKAGES[2]["tokens"] == 550
    assert _TOPUP_PACKAGES[2]["tokens"] > 50 * GEO_TOKENS_PER_EURO


def test_admin_allowlist_matches_credit_cents():
    assert ADMIN_TOPUP_AMOUNTS_CENTS == {p["credit_cents"] for p in _TOPUP_PACKAGES}
    assert {p["cents"] for p in _TOPUP_PACKAGES} == set(_TOPUP_ENV.keys())


def test_plus_includes_100_tokens_monthly():
    assert PLUS_MONTHLY_TOKENS == 100
    assert tokens_to_cents(PLUS_MONTHLY_TOKENS) == 1000


def test_topup_requires_paid_plan():
    free = User(email="free@ex.com", plan="free")
    plus = User(email="plus@ex.com", plan="plus")
    biz = User(email="biz@ex.com", plan="business")
    admin = User(email="admin@ex.com", plan="admin")
    assert _user_can_purchase_topup(free) is False
    assert _user_can_purchase_topup(None) is False
    assert _user_can_purchase_topup(plus) is True
    assert _user_can_purchase_topup(biz) is True
    assert _user_can_purchase_topup(admin) is True
