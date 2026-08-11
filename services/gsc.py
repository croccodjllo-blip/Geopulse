"""GSC integration scaffold (requires GOOGLE_OAUTH credentials)."""

from __future__ import annotations

import os
from typing import Any

GSC_CLIENT_ID = (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
GSC_CLIENT_SECRET = (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()


def gsc_configured() -> bool:
    return bool(GSC_CLIENT_ID and GSC_CLIENT_SECRET)


def gsc_status() -> dict[str, Any]:
    """Honesty: never claim available until an end-to-end OAuth connect exists."""
    if not gsc_configured():
        return {
            "available": False,
            "connected": False,
            "reason": "Imposta GOOGLE_OAUTH_CLIENT_ID e GOOGLE_OAUTH_CLIENT_SECRET.",
            "note": "Integrazione GSC non ancora collegabile end-to-end.",
        }
    # Client credentials alone do not mean the product can connect a property.
    return {
        "available": False,
        "connected": False,
        "reason": "OAuth client configurato, ma il flusso di collegamento GSC non è ancora attivo.",
        "note": "Nascondiamo il connector finché non esiste connect end-to-end.",
    }
