"""Google Search Console OAuth connect (Plus/Business).

Stores sealed refresh/access tokens on the user row. Connect is available when
``GOOGLE_OAUTH_CLIENT_ID`` + ``GOOGLE_OAUTH_CLIENT_SECRET`` are set; ``connected``
is true only after a successful callback with a refresh token.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from services.webhook_crypto import reveal_webhook_secret, seal_webhook_secret

logger = logging.getLogger(__name__)

GSC_CLIENT_ID = (os.getenv("GOOGLE_OAUTH_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID") or "").strip()
GSC_CLIENT_SECRET = (
    os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET") or ""
).strip()

GSC_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GSC_TOKEN_URL = "https://oauth2.googleapis.com/token"
GSC_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GSC_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GSC_SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"
GSC_SCOPES = "https://www.googleapis.com/auth/webmasters.readonly openid email"


def reload_gsc_env() -> None:
    """Refresh module-level client credentials (tests / after dotenv)."""
    global GSC_CLIENT_ID, GSC_CLIENT_SECRET
    GSC_CLIENT_ID = (
        os.getenv("GOOGLE_OAUTH_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID") or ""
    ).strip()
    GSC_CLIENT_SECRET = (
        os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET") or ""
    ).strip()


def gsc_configured() -> bool:
    return bool(GSC_CLIENT_ID and GSC_CLIENT_SECRET)


def gsc_redirect_uri() -> str:
    """Public callback URL registered in Google Cloud Console."""
    from app import absolute_url

    return absolute_url("gsc_oauth_callback")


def build_authorization_url(*, state: str, redirect_uri: str | None = None) -> str:
    if not gsc_configured():
        raise RuntimeError("Google OAuth client non configurato")
    params = {
        "client_id": GSC_CLIENT_ID,
        "redirect_uri": redirect_uri or gsc_redirect_uri(),
        "response_type": "code",
        "scope": GSC_SCOPES,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{GSC_AUTH_URL}?{urlencode(params)}"


def new_oauth_state() -> str:
    return secrets.token_urlsafe(24)


def exchange_code_for_tokens(
    code: str,
    *,
    redirect_uri: str | None = None,
) -> dict[str, Any]:
    """Exchange authorization code → token payload (raises on failure)."""
    if not gsc_configured():
        raise RuntimeError("Google OAuth client non configurato")
    data = {
        "code": code,
        "client_id": GSC_CLIENT_ID,
        "client_secret": GSC_CLIENT_SECRET,
        "redirect_uri": redirect_uri or gsc_redirect_uri(),
        "grant_type": "authorization_code",
    }
    res = requests.post(GSC_TOKEN_URL, data=data, timeout=30)
    payload = {}
    try:
        payload = res.json() if res.content else {}
    except Exception:
        payload = {}
    if res.status_code >= 400 or not isinstance(payload, dict):
        err = payload.get("error_description") or payload.get("error") or res.text[:200]
        raise RuntimeError(f"Token exchange failed: {err}")
    if not payload.get("access_token"):
        raise RuntimeError("Token exchange: missing access_token")
    return payload


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    if not gsc_configured():
        raise RuntimeError("Google OAuth client non configurato")
    data = {
        "client_id": GSC_CLIENT_ID,
        "client_secret": GSC_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    res = requests.post(GSC_TOKEN_URL, data=data, timeout=30)
    payload = {}
    try:
        payload = res.json() if res.content else {}
    except Exception:
        payload = {}
    if res.status_code >= 400 or not isinstance(payload, dict):
        err = payload.get("error_description") or payload.get("error") or res.text[:200]
        raise RuntimeError(f"Token refresh failed: {err}")
    return payload


def fetch_account_email(access_token: str) -> str:
    try:
        res = requests.get(
            GSC_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        if res.status_code >= 400:
            return ""
        data = res.json() if res.content else {}
        return str((data or {}).get("email") or "").strip()
    except Exception:
        logger.exception("GSC userinfo failed")
        return ""


def list_gsc_sites(access_token: str) -> list[str]:
    """Return Search Console property URLs the account can access."""
    try:
        res = requests.get(
            GSC_SITES_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        if res.status_code >= 400:
            logger.warning("GSC sites list HTTP %s", res.status_code)
            return []
        data = res.json() if res.content else {}
        entries = data.get("siteEntry") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            return []
        out: list[str] = []
        for row in entries:
            if not isinstance(row, dict):
                continue
            url = str(row.get("siteUrl") or "").strip()
            if url and url not in out:
                out.append(url)
        return out[:50]
    except Exception:
        logger.exception("GSC sites list failed")
        return []


def revoke_token(token: str) -> None:
    tok = (token or "").strip()
    if not tok:
        return
    try:
        requests.post(GSC_REVOKE_URL, data={"token": tok}, timeout=15)
    except Exception:
        logger.exception("GSC token revoke failed")


def user_has_gsc_connection(user: Any) -> bool:
    return bool((getattr(user, "gsc_refresh_token", None) or "").strip())


def clear_gsc_connection(user: Any) -> None:
    user.gsc_refresh_token = None
    user.gsc_access_token = None
    user.gsc_token_expires_at = None
    user.gsc_account_email = None
    user.gsc_connected_at = None
    user.gsc_site_urls_json = ""


def apply_token_payload(user: Any, payload: dict[str, Any], *, keep_refresh: bool = True) -> None:
    """Seal and store tokens from Google token endpoint payload onto ``user``."""
    access = str(payload.get("access_token") or "").strip()
    refresh = str(payload.get("refresh_token") or "").strip()
    if access:
        user.gsc_access_token = seal_webhook_secret(access)
    if refresh:
        user.gsc_refresh_token = seal_webhook_secret(refresh)
    elif not keep_refresh and not (getattr(user, "gsc_refresh_token", None) or "").strip():
        raise RuntimeError(
            "Google non ha restituito un refresh token. "
            "Revoca l’accesso Centropic in account Google e riprova."
        )
    expires_in = payload.get("expires_in")
    try:
        seconds = int(expires_in) if expires_in is not None else 3600
    except (TypeError, ValueError):
        seconds = 3600
    user.gsc_token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=max(60, seconds - 30)
    )
    if not getattr(user, "gsc_connected_at", None):
        user.gsc_connected_at = datetime.now(timezone.utc)


def reveal_gsc_refresh(user: Any) -> str:
    return reveal_webhook_secret(getattr(user, "gsc_refresh_token", None))


def reveal_gsc_access(user: Any) -> str:
    return reveal_webhook_secret(getattr(user, "gsc_access_token", None))


def ensure_fresh_access_token(user: Any, db_session: Any | None = None) -> str:
    """Return a usable access token, refreshing when expired."""
    access = reveal_gsc_access(user)
    expires = getattr(user, "gsc_token_expires_at", None)
    now = datetime.now(timezone.utc)
    if expires is not None and getattr(expires, "tzinfo", None) is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if access and expires and expires > now + timedelta(seconds=60):
        return access
    refresh = reveal_gsc_refresh(user)
    if not refresh:
        raise RuntimeError("GSC non collegato")
    payload = refresh_access_token(refresh)
    apply_token_payload(user, payload, keep_refresh=True)
    if db_session is not None:
        db_session.commit()
    return reveal_gsc_access(user)


def persist_connection_from_code(
    user: Any,
    code: str,
    *,
    redirect_uri: str | None = None,
    db_session: Any | None = None,
) -> dict[str, Any]:
    """Complete OAuth callback: exchange code, seal tokens, list properties."""
    payload = exchange_code_for_tokens(code, redirect_uri=redirect_uri)
    if not payload.get("refresh_token") and not (getattr(user, "gsc_refresh_token", None) or "").strip():
        # Re-consent required for first connect.
        raise RuntimeError(
            "Manca il refresh token. In Google Account → Sicurezza → Accesso terze parti "
            "rimuovi Centropic, poi collega di nuovo con consenso completo."
        )
    apply_token_payload(user, payload, keep_refresh=True)
    access = reveal_gsc_access(user)
    email = fetch_account_email(access)
    if email:
        user.gsc_account_email = email[:255]
    sites = list_gsc_sites(access)
    user.gsc_site_urls_json = json.dumps(sites, ensure_ascii=False)
    user.gsc_connected_at = datetime.now(timezone.utc)
    if db_session is not None:
        db_session.commit()
    return {
        "email": user.gsc_account_email or "",
        "sites": sites,
    }


def disconnect_user(user: Any, *, db_session: Any | None = None) -> None:
    refresh = reveal_gsc_refresh(user)
    access = reveal_gsc_access(user)
    revoke_token(refresh or access)
    clear_gsc_connection(user)
    if db_session is not None:
        db_session.commit()


def gsc_status(user: Any | None = None) -> dict[str, Any]:
    """Template/API status for Settings → Connector."""
    if not gsc_configured():
        return {
            "available": False,
            "connected": False,
            "reason": "Imposta GOOGLE_OAUTH_CLIENT_ID e GOOGLE_OAUTH_CLIENT_SECRET.",
            "note": "Integrazione GSC non ancora collegabile.",
            "email": None,
            "sites": [],
            "redirect_uri": None,
        }
    connected = bool(user is not None and user_has_gsc_connection(user))
    sites: list[str] = []
    email = None
    if connected and user is not None:
        email = getattr(user, "gsc_account_email", None) or None
        raw = getattr(user, "gsc_site_urls_json", None) or ""
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    sites = [str(x) for x in parsed if x][:20]
            except Exception:
                sites = []
    try:
        redirect = gsc_redirect_uri()
    except Exception:
        redirect = None
    if connected:
        note = (
            f"Collegato come {email}."
            if email
            else "Account Google collegato a Search Console (sola lettura)."
        )
        if sites:
            note += f" Proprietà visibili: {len(sites)}."
        reason = "Connesso"
    else:
        reason = "Pronto per il collegamento OAuth"
        note = "Collega Google Search Console (sola lettura) per questo account."
    return {
        "available": True,
        "connected": connected,
        "reason": reason,
        "note": note,
        "email": email,
        "sites": sites,
        "redirect_uri": redirect,
    }
