"""Encrypt alert webhook secrets at rest (reversible for HMAC signing).

Outbound webhooks need the raw shared secret to compute
``X-Centropic-Signature``. Hashing alone would break signing, so we seal with
Fernet derived from ``WEBHOOK_SECRET_FERNET_KEY`` or ``FLASK_SECRET_KEY``.

Wire format: ``enc:v1:<fernet-token>``. Legacy plaintext rows are still
accepted when revealing and can be upgraded on next write / lazy migrate.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_SEAL_PREFIX = "enc:v1:"
_FERNET = None
_FERNET_FAILED = False


def _fernet():
    """Lazy Fernet from dedicated key or Flask secret (HKDF-shaped derive)."""
    global _FERNET, _FERNET_FAILED
    if _FERNET is not None:
        return _FERNET
    if _FERNET_FAILED:
        return None
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        logger.error("cryptography package missing; cannot seal webhook secrets")
        _FERNET_FAILED = True
        return None
    raw = (
        (os.getenv("WEBHOOK_SECRET_FERNET_KEY") or "").strip()
        or (os.getenv("FLASK_SECRET_KEY") or "").strip()
    )
    if not raw:
        logger.error("No WEBHOOK_SECRET_FERNET_KEY/FLASK_SECRET_KEY for sealing")
        _FERNET_FAILED = True
        return None
    # Fernet key must be 32 url-safe base64-encoded bytes.
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    _FERNET = Fernet(key)
    return _FERNET


def reset_webhook_crypto_for_tests() -> None:
    global _FERNET, _FERNET_FAILED
    _FERNET = None
    _FERNET_FAILED = False


def is_sealed_webhook_secret(stored: str | None) -> bool:
    return bool(stored) and str(stored).startswith(_SEAL_PREFIX)


def webhook_secret_is_set(stored: str | None) -> bool:
    return bool((stored or "").strip())


def seal_webhook_secret(raw: str) -> str:
    """Encrypt raw secret for DB storage. Raises RuntimeError if crypto unavailable."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty webhook secret")
    f = _fernet()
    if f is None:
        raise RuntimeError("webhook secret encryption unavailable")
    token = f.encrypt(text.encode("utf-8")).decode("ascii")
    return f"{_SEAL_PREFIX}{token}"


def reveal_webhook_secret(stored: str | None) -> str:
    """Return plaintext secret for HMAC signing.

    Sealed values are decrypted. Legacy plaintext is returned as-is so existing
    rows keep working until upgraded.
    """
    text = (stored or "").strip()
    if not text:
        return ""
    if not text.startswith(_SEAL_PREFIX):
        return text
    f = _fernet()
    if f is None:
        logger.error("cannot reveal sealed webhook secret: crypto unavailable")
        return ""
    token = text[len(_SEAL_PREFIX) :]
    try:
        from cryptography.fernet import InvalidToken

        return f.decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        logger.error("webhook secret decrypt failed (InvalidToken)")
        return ""
    except Exception:
        logger.exception("webhook secret decrypt failed")
        return ""


def store_webhook_secret(raw: str | None) -> str | None:
    """Normalize form input → sealed DB value (or None to clear)."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text in {"-", "clear", "DELETE"}:
        return None
    return seal_webhook_secret(text)


def upgrade_webhook_secret_if_plaintext(user: Any, db_session: Any | None) -> bool:
    """If ``user.webhook_secret`` is legacy plaintext, re-seal and optionally commit.

    Returns True when the row was upgraded.
    """
    stored = getattr(user, "webhook_secret", None)
    if not webhook_secret_is_set(stored) or is_sealed_webhook_secret(stored):
        return False
    raw = str(stored).strip()
    try:
        sealed = seal_webhook_secret(raw)
    except Exception:
        logger.exception(
            "webhook secret upgrade failed user=%s", getattr(user, "id", None)
        )
        return False
    user.webhook_secret = sealed
    if db_session is not None:
        try:
            db_session.commit()
        except Exception:
            logger.exception(
                "webhook secret upgrade commit failed user=%s",
                getattr(user, "id", None),
            )
            try:
                db_session.rollback()
            except Exception:
                pass
            return False
    return True
