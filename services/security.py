"""Security helpers: safe redirects and output sanitization."""

from __future__ import annotations

import os
from html import escape
from urllib.parse import urlparse

from flask import Request


def safe_next_url(candidate: str | None, *, fallback: str = "/") -> str:
    """
    Allow only same-origin relative paths.

    Rejects scheme-relative open redirects like //evil.test and absolute URLs.
    """
    if not candidate:
        return fallback
    value = candidate.strip()
    if not value.startswith("/") or value.startswith("//"):
        return fallback
    if "\\" in value or "\n" in value or "\r" in value:
        return fallback
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return fallback
    # Keep query/fragment for local paths only.
    return value


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

    # Relative path — same rules as safe_next_url.
    if candidate.startswith("/") and not candidate.startswith("//"):
        if "\\" in candidate or "://" in candidate:
            return None
        parsed_rel = urlparse(candidate)
        if parsed_rel.scheme or parsed_rel.netloc:
            return None
        return candidate

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
