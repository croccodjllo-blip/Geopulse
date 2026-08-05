"""HTTP view layer — domain-scoped route modules.

Each module exposes ``register(app, runtime)`` and keeps legacy endpoint
names so templates continue to use ``url_for('dashboard')`` etc.
"""

from __future__ import annotations

from typing import Any

from flask import Flask

_REGISTERED = False


def register_all_views(app: Flask, runtime: Any) -> None:
    """Attach domain view modules. Safe to call multiple times."""
    global _REGISTERED
    if getattr(app, "_centropic_views_registered", False):
        return

    from centropic.views import (
        admin,
        api,
        auth,
        billing,
        dashboard,
        edge,
        marketing,
        wellknown,
    )

    for mod in (wellknown, edge, marketing, billing, auth, dashboard, api, admin):
        if hasattr(mod, "register"):
            mod.register(app, runtime)

    app._centropic_views_registered = True  # type: ignore[attr-defined]
    _REGISTERED = True
