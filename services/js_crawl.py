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


def _allow_request(url: str) -> bool:
    scheme = (url or "").split(":", 1)[0].lower()
    if scheme in {"data", "blob", "file", "ftp", "ws", "wss"}:
        return False
    try:
        assert_public_http_url(url, resolve=True)
        return True
    except UnsafeURLError:
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
            context = browser.new_context(
                java_script_enabled=True,
                ignore_https_errors=False,
            )
            page = context.new_page()

            def _on_route(route):  # type: ignore[no-untyped-def]
                req_url = route.request.url
                # Block non-document subresources that are not public HTTP(S).
                if not _allow_request(req_url):
                    return route.abort()
                return route.continue_()

            page.route("**/*", _on_route)
            page.goto(safe_url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Re-validate final URL after redirects (DNS rebinding / open redirect).
            try:
                assert_public_http_url(page.url, resolve=True)
            except UnsafeURLError as exc:
                context.close()
                browser.close()
                return {
                    "ok": False,
                    "html": "",
                    "error": f"ssrf_blocked_final:{exc}"[:200],
                    "mode": "ssrf_blocked",
                }
            # Cap wait: avoid hanging forever on noisy SPAs.
            try:
                page.wait_for_load_state("networkidle", timeout=min(8000, timeout_ms))
            except Exception:
                pass
            html = page.content()
            context.close()
            browser.close()
        return {"ok": True, "html": html, "error": None, "mode": "playwright"}
    except Exception as exc:
        logger.exception("js render failed")
        return {"ok": False, "html": "", "error": str(exc)[:200], "mode": "error"}
