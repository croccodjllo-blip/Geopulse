"""Token top-up package pricing invariants."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-token-pricing")

from app import (  # noqa: E402
    ADMIN_TOPUP_AMOUNTS_CENTS,
    GEO_TOKEN_EUR_CENTS,
    GEO_TOKENS_PER_EURO,
    _TOPUP_PACKAGES,
)
from services.paddle_billing import _TOPUP_ENV


def test_geo_token_rate():
    assert GEO_TOKEN_EUR_CENTS == 1
    assert GEO_TOKENS_PER_EURO == 100
    assert 1000 * GEO_TOKEN_EUR_CENTS == 1000  # €10 pack → 1000 token


def test_public_packages_are_10_20_50_euro():
    cents = [p["cents"] for p in _TOPUP_PACKAGES]
    assert cents == [1000, 2000, 5000]
    for p in _TOPUP_PACKAGES:
        assert p["tokens"] == p["cents"]
        assert p["tokens"] == p["price_eur"] * GEO_TOKENS_PER_EURO
        assert p["cents"] == p["price_eur"] * 100


def test_admin_and_paddle_catalog_match_packages():
    package_cents = {p["cents"] for p in _TOPUP_PACKAGES}
    assert package_cents == set(ADMIN_TOPUP_AMOUNTS_CENTS)
    assert package_cents == set(_TOPUP_ENV.keys())
