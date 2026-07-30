#!/usr/bin/env python3
"""Create Centropic catalog prices in Paddle (sandbox or live).

Requires:
  PADDLE_API_KEY
  PADDLE_ENV=sandbox|production

Creates (if missing by name):
  - Product "Centropic Plus" + monthly price
  - Product "Centropic Credits" + one-time prices for €1/5/10/50/100

Prints env lines to paste into .env. Does not write secrets.
"""

from __future__ import annotations

import json
import os
import sys

import requests

ENV = (os.getenv("PADDLE_ENV") or "sandbox").strip().lower()
API_KEY = (os.getenv("PADDLE_API_KEY") or "").strip()
BASE = (
    "https://sandbox-api.paddle.com"
    if ENV in {"sandbox", "test"}
    else "https://api.paddle.com"
)

TOPUPS = [
    (100, "Crediti €1"),
    (500, "Crediti €5"),
    (1000, "Crediti €10"),
    (5000, "Crediti €50"),
    (10000, "Crediti €100"),
]


def api(method: str, path: str, payload: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    res = requests.request(
        method, f"{BASE}{path}", headers=headers, json=payload, timeout=45
    )
    if res.status_code >= 400:
        raise SystemExit(f"Paddle {method} {path} → {res.status_code}: {res.text[:500]}")
    return res.json()


def find_product(name: str) -> dict | None:
    data = api("GET", "/products?per_page=50").get("data") or []
    for p in data:
        if (p.get("name") or "").strip().lower() == name.lower():
            return p
    return None


def ensure_product(name: str, tax_category: str = "standard") -> dict:
    existing = find_product(name)
    if existing:
        return existing
    return api(
        "POST",
        "/products",
        {"name": name, "tax_category": tax_category, "description": name},
    ).get("data") or {}


def ensure_price(
    *,
    product_id: str,
    name: str,
    unit_price_cents: int,
    currency: str = "EUR",
    billing_cycle: dict | None = None,
) -> dict:
    # List prices for product and match by name.
    prices = api("GET", f"/prices?product_id={product_id}&per_page=50").get("data") or []
    for p in prices:
        if (p.get("name") or "").strip().lower() == name.lower():
            return p
    payload: dict = {
        "product_id": product_id,
        "description": name,
        "name": name,
        "unit_price": {"amount": str(int(unit_price_cents)), "currency_code": currency},
        "quantity": {"minimum": 1, "maximum": 1},
    }
    if billing_cycle:
        payload["billing_cycle"] = billing_cycle
    return api("POST", "/prices", payload).get("data") or {}


def main() -> int:
    if not API_KEY:
        print("Set PADDLE_API_KEY (and optionally PADDLE_ENV=sandbox)", file=sys.stderr)
        return 2

    plus_product = ensure_product("Centropic Plus")
    # Default Plus at €49/month — adjust in Paddle dashboard if needed.
    plus_price = ensure_price(
        product_id=plus_product["id"],
        name="Plus monthly",
        unit_price_cents=4900,
        billing_cycle={"interval": "month", "frequency": 1},
    )

    credits_product = ensure_product("Centropic Credits")
    topup_ids: dict[int, str] = {}
    for cents, label in TOPUPS:
        price = ensure_price(
            product_id=credits_product["id"],
            name=label,
            unit_price_cents=cents,
            billing_cycle=None,
        )
        topup_ids[cents] = price["id"]

    print("# Paste into /opt/aio-bot/.env (and restart aio-bot)")
    print(f"PADDLE_ENV={ENV if ENV in {'sandbox','production'} else 'sandbox'}")
    print(f"PADDLE_PRICE_PLUS_MONTHLY={plus_price['id']}")
    for cents, pid in topup_ids.items():
        print(f"PADDLE_PRICE_TOPUP_{cents}={pid}")
    print("# Also set: PADDLE_API_KEY, PADDLE_CLIENT_TOKEN, PADDLE_WEBHOOK_SECRET")
    print("# Webhook: https://centropic.ai/billing/paddle-webhook")
    print(json.dumps({"plus": plus_price["id"], "topups": topup_ids}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
