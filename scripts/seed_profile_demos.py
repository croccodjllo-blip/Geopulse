#!/usr/bin/env python3
"""Crea/aggiorna 3 utenze demo Free / Plus / Business con uso illimitato.

Ogni utente resta sul proprio piano (feature gate fedele) ma ha:
  - role=internal → crediti illimitati (usage_billing.is_unlimited_user)
  - email verificata
  - quote siti/analisi bypassate via is_unlimited_user

Password:
  DEMO_PROFILE_PASSWORD  — stessa password per tutte e tre (consigliata in prod)
  oppure DEMO_FREE_PASSWORD / DEMO_PLUS_PASSWORD / DEMO_BUSINESS_PASSWORD
  Se nessuna è impostata, genera password casuali e le stampa una sola volta.
"""

from __future__ import annotations

import os
import secrets
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import User, app, db, ensure_schema  # noqa: E402

PROFILES = (
    {
        "key": "free",
        "email": (os.getenv("DEMO_FREE_EMAIL") or "free@centropic.ai").strip().lower(),
        "name": "free",
        "plan": "free",
        "password_env": "DEMO_FREE_PASSWORD",
    },
    {
        "key": "plus",
        "email": (os.getenv("DEMO_PLUS_EMAIL") or "plus@centropic.ai").strip().lower(),
        "name": "plus",
        "plan": "plus",
        "password_env": "DEMO_PLUS_PASSWORD",
    },
    {
        "key": "business",
        "email": (os.getenv("DEMO_BUSINESS_EMAIL") or "business@centropic.ai")
        .strip()
        .lower(),
        "name": "business",
        "plan": "business",
        "password_env": "DEMO_BUSINESS_PASSWORD",
    },
)


def _password_for(profile: dict) -> str:
    shared = (os.getenv("DEMO_PROFILE_PASSWORD") or "").strip()
    if shared:
        return shared
    specific = (os.getenv(profile["password_env"]) or "").strip()
    if specific:
        return specific
    return secrets.token_urlsafe(14)


def upsert_profile(profile: dict, password: str) -> User:
    email = profile["email"]
    user = User.query.filter_by(email=email).first()
    created = user is None
    if created:
        user = User(
            email=email,
            name=profile["name"],
            plan=profile["plan"],
            role="internal",
            company="Centropic Demo",
        )
        user.set_password(password)
        db.session.add(user)
    else:
        user.name = profile["name"]
        user.plan = profile["plan"]
        user.role = "internal"
        if not (user.company or "").strip():
            user.company = "Centropic Demo"
        # Reset password when DEMO_* env is set, or always on --reset-passwords.
        reset = (
            os.getenv("DEMO_PROFILE_RESET", "0") == "1"
            or "--reset-passwords" in sys.argv
            or bool((os.getenv("DEMO_PROFILE_PASSWORD") or "").strip())
            or bool((os.getenv(profile["password_env"]) or "").strip())
        )
        if reset or created:
            user.set_password(password)
        else:
            password = "(invariata — passa --reset-passwords o DEMO_PROFILE_PASSWORD)"

    user.email_verified_at = datetime.now(timezone.utc)
    user.verify_token_hash = None
    user.verify_token_expires = None
    # Sentinel balance for UI; billing still skips debit for internal.
    if int(getattr(user, "credit_balance_cents", 0) or 0) < 1_000_000:
        user.credit_balance_cents = 1_000_000
    user.credit_held_cents = 0
    db.session.commit()
    user._seed_password_display = password  # type: ignore[attr-defined]
    user._seed_created = created  # type: ignore[attr-defined]
    return user


def main() -> None:
    if os.getenv("ALLOW_DEMO_SEED", "0") != "1":
        print(
            "ERROR: set ALLOW_DEMO_SEED=1 to create unlimited demo profiles "
            "(role=internal bypasses billing).",
            file=sys.stderr,
        )
        raise SystemExit(2)
    with app.app_context():
        ensure_schema()
        print("Seed utenze profilo (role=internal, quote illimitate, gate piano fedele)")
        print("-" * 60)
        for profile in PROFILES:
            password = _password_for(profile)
            user = upsert_profile(profile, password)
            pwd = getattr(user, "_seed_password_display", "(n/d)")
            action = "creata" if getattr(user, "_seed_created", False) else "aggiornata"
            print(f"[{profile['key']}] {action}")
            print(f"  email:    {user.email}")
            print(f"  name:     {user.name}")
            print(f"  plan:     {user.plan}")
            print(f"  role:     {user.role}")
            print(f"  label:    {user.plan_label}")
            print(f"  is_pro:   {user.is_pro}")
            print(f"  is_biz:   {user.is_business}")
            print(f"  is_admin: {user.is_admin}")
            print(f"  password: {pwd}")
            print()
        print("Login: https://centropic.ai/login")
        print("Nota: non sono admin panel — restano sul piano indicato.")


if __name__ == "__main__":
    main()
