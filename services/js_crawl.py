"""Optional JS-rendered crawl mode (Playwright). Falls back to static HTML."""

from __future__ import annotations

import logging
import os
from typing import Any

from services.ssrf import UnsafeURLError, assert_public_http_url

logger = logging.getLogger(__name__)

JS_CRAWL_ENABLED = (os.getenv("JS_CRAWL_ENABLED") or "").strip() in {"1", "true", "yes"}


def js_crawl_available() -> bool:
    if not JS_CRAWL_ENABLED:
        return False
    try:
        import playwright  # noqa: F401

        return True
    except Exception:
        return False


def render_html(url: str, *, timeout_ms: int = 15000) -> dict[str, Any]:
    """Fetch page HTML after JS render. Returns {ok, html, error}."""
    if not js_crawl_available():
        return {
            "ok": False,
            "html": "",
            "error": "JS crawl disabilitato o Playwright non installato (JS_CRAWL_ENABLED=1).",
            "mode": "static_fallback",
        }
    try:
        safe_url = assert_public_http_url(url, resolve=True)
    except UnsafeURLError as exc:
        return {
            "ok": False,
            "html": "",
            "error": f"ssrf_blocked:{exc}"[:200],
            "mode": "ssrf_blocked",
        }
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(safe_url, wait_until="networkidle", timeout=timeout_ms)
            html = page.content()
            browser.close()
        return {"ok": True, "html": html, "error": None, "mode": "playwright"}
    except Exception as exc:
        logger.exception("js render failed")
        return {"ok": False, "html": "", "error": str(exc)[:200], "mode": "error"}
