"""Security helpers: safe redirects and output sanitization."""

from __future__ import annotations

from html import escape
from urllib.parse import urlparse


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


def html_attr(value: str | None) -> str:
    """Escape a value for use inside an HTML attribute or text node."""
    return escape("" if value is None else str(value), quote=True)


def csv_cell(value: object) -> str:
    """Neutralize spreadsheet formula injection in CSV cells."""
    text = "" if value is None else str(value)
    if text[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + text
    return text
