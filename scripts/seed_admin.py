#!/usr/bin/env python3
"""Crea/aggiorna l'utente admin di prova con piano Pro/admin."""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import ADMIN_EMAIL, ADMIN_PASSWORD, app, ensure_admin_user, ensure_schema  # noqa: E402


def main() -> None:
    with app.app_context():
        ensure_schema()
        user = ensure_admin_user()
        print("Admin pronto")
        print(f"  email: {user.email}")
        print(f"  plan:  {user.plan}")
        print(f"  name:  {user.name}")
        print(f"  password env ADMIN_PASSWORD (default usata se non impostata)")
        print(f"  login: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")


if __name__ == "__main__":
    main()
