"""API key helpers for the public Centropic API."""

from __future__ import annotations

import hashlib
import secrets
from typing import Any


def generate_api_key() -> tuple[str, str, str]:
    """Return (raw_key, prefix, sha256_hash)."""
    raw = "ct_" + secrets.token_urlsafe(32)
    prefix = raw[:10]
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, prefix, digest


def hash_api_key(raw: str) -> str:
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


def find_user_by_api_key(User: Any, raw_key: str) -> Any | None:
    raw_key = (raw_key or "").strip()
    if not raw_key.startswith(("ct_", "gp_")):
        return None
    digest = hash_api_key(raw_key)
    return User.query.filter_by(api_key_hash=digest).first()
