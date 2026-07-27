#!/usr/bin/env python3
"""Crea/aggiorna l'utente admin (richiede ADMIN_PASSWORD in env)."""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import (  # noqa: E402
    ADMIN_BOOTSTRAP,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    app,
    ensure_admin_user,
    ensure_schema,
)


def main() -> None:
    if not ADMIN_PASSWORD:
        print("ERROR: imposta ADMIN_PASSWORD nell'ambiente / .env", file=sys.stderr)
        raise SystemExit(1)
    # seed_admin forza bootstrap password
    os.environ["ADMIN_BOOTSTRAP"] = "1"
    with app.app_context():
        ensure_schema()
        # re-read flag after env set — function uses module-level ADMIN_BOOTSTRAP
        import app as app_mod

        app_mod.ADMIN_BOOTSTRAP = True
        user = ensure_admin_user()
    if user is None:
        print("ERROR: admin non creato", file=sys.stderr)
        raise SystemExit(1)
    print("Admin pronto")
    print(f"  email: {user.email}")
    print(f"  plan:  {user.plan}")
    print(f"  name:  {user.name}")
    print(f"  password: (valore di ADMIN_PASSWORD — non stampata)")
    print(f"  bootstrap: {ADMIN_BOOTSTRAP} (seed forza reset)")
    print(f"  login: {ADMIN_EMAIL}")


if __name__ == "__main__":
    main()
