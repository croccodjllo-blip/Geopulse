"""GSC integration scaffold (requires GOOGLE_OAUTH credentials)."""

from __future__ import annotations

import os
from typing import Any

GSC_CLIENT_ID = (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
GSC_CLIENT_SECRET = (os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()


def gsc_configured() -> bool:
    return bool(GSC_CLIENT_ID and GSC_CLIENT_SECRET)


def gsc_status() -> dict[str, Any]:
    if not gsc_configured():
        return {
            "available": False,
            "reason": "Imposta GOOGLE_OAUTH_CLIENT_ID e GOOGLE_OAUTH_CLIENT_SECRET.",
            "note": "Scaffold pronto: OAuth → Search Analytics + sitemap coverage.",
        }
    return {
        "available": True,
        "connected": False,
        "note": "OAuth client presente: collega la property Search Console dal dashboard Plus.",
    }
