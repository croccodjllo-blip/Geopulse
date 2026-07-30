"""Security helpers: safe redirects, password policy, output sanitization."""

from __future__ import annotations

import os
import re
from html import escape
from urllib.parse import unquote, urlparse

from flask import Request

# Password policy: length + complexity (letter + digit). Shared by register/reset/settings.
PASSWORD_MIN_LEN = 10
PASSWORD_MAX_LEN = 128
_PASSWORD_HAS_LETTER = re.compile(r"[A-Za-z]")
_PASSWORD_HAS_DIGIT = re.compile(r"\d")


def password_policy_error(password: str | None) -> str | None:
    """Return an Italian error message if *password* fails policy, else None."""
    value = password or ""
    if len(value) < PASSWORD_MIN_LEN:
        return f"La password deve avere almeno {PASSWORD_MIN_LEN} caratteri."
    if len(value) > PASSWORD_MAX_LEN:
        return f"La password non può superare {PASSWORD_MAX_LEN} caratteri."
    if not _PASSWORD_HAS_LETTER.search(value):
        return "La password deve contenere almeno una lettera."
    if not _PASSWORD_HAS_DIGIT.search(value):
        return "La password deve contenere almeno un numero."
    return None


def _fully_unquote(value: str, *, rounds: int = 4) -> str:
    """Decode percent-encoding repeatedly to catch nested open-redirect tricks."""
    prev = value
    for _ in range(max(1, rounds)):
        cur = unquote(prev)
        if cur == prev:
            break
        prev = cur
    return prev


def safe_next_url(candidate: str | None, *, fallback: str = "/") -> str:
    """
    Allow only same-origin relative paths.

    Rejects scheme-relative open redirects like //evil.test, absolute URLs,
    and encoded variants such as /%2f%2fevil.test.
    """
    if not candidate:
        return fallback
    raw = candidate.strip()
    if not raw:
        return fallback
    # Inspect both raw and fully-decoded forms so %2f tricks cannot slip through.
    for value in (raw, _fully_unquote(raw)):
        if not value.startswith("/") or value.startswith("//"):
            return fallback
        if "\\" in value or "\n" in value or "\r" in value or "\x00" in value:
            return fallback
        # Collapse accidental multi-slash after decoding (///evil → netloc).
        parsed = urlparse(value)
        if parsed.scheme or parsed.netloc:
            return fallback
        # Extra guard: path must stay relative (no authority via "///host").
        if value.startswith("///"):
            return fallback
    # Return the original relative path (keep query/fragment as submitted).
    if not raw.startswith("/") or raw.startswith("//"):
        return fallback
    return raw


def safe_same_origin_url(candidate: str | None, request: Request) -> str | None:
    """Return *candidate* only if it is a same-origin relative or absolute URL.

    Rejects protocol-relative URLs and host-prefix tricks
    (``https://centropic.ai.evil.com`` must not match ``https://centropic.ai``).
    Hostname comparison is exact against ``request.host`` and ``PUBLIC_SITE_URL``.
    """
    if not candidate:
        return None
    candidate = candidate.strip()
    if not candidate or "\n" in candidate or "\r" in candidate:
        return None
    if candidate.startswith("//"):
        return None

    # Relative path — same rules as safe_next_url (including encoded // tricks).
    if candidate.startswith("/") and not candidate.startswith("//"):
        rel = safe_next_url(candidate, fallback="")
        return rel or None

    try:
        parsed = urlparse(candidate)
    except Exception:
        return None

    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None

    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return None

    allowed: set[str] = set()
    req_host = (request.host or "").split(":")[0].lower().rstrip(".")
    if req_host:
        allowed.add(req_host)
    public = (os.environ.get("PUBLIC_SITE_URL") or "").strip()
    if public:
        try:
            pub_host = (urlparse(public).hostname or "").lower().rstrip(".")
            if pub_host:
                allowed.add(pub_host)
        except Exception:
            pass

    if host not in allowed:
        return None

    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    if parsed.fragment:
        path = f"{path}#{parsed.fragment}"
    return path


def html_attr(value: str | None) -> str:
    """Escape a value for use inside an HTML attribute or text node."""
    return escape("" if value is None else str(value), quote=True)


def csv_cell(value: object) -> str:
    """Neutralize spreadsheet formula injection in CSV cells."""
    text = "" if value is None else str(value)
    if text[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + text
    return text
