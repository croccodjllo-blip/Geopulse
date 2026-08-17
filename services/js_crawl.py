"""Optional JS-rendered crawl mode (Playwright). Falls back to static HTML.

DNS is pinned via Chromium ``--host-resolver-rules`` so Playwright connects to the
same public IP that ``assert_public_http_url`` validated (mitigates rebinding).
"""

from __future__ import annotations

import ipaddress
import logging
import os
from typing import Any
from urllib.parse import urlparse

from services.ssrf import UnsafeURLError, assert_public_http_url, resolve_public_ips

logger = logging.getLogger(__name__)

def _env_enabled() -> bool:
    return (os.getenv("JS_CRAWL_ENABLED") or "").strip().lower() in {"1", "true", "yes"}


# Legacy alias (evaluated at import; prefer js_crawl_available() which re-reads env).
JS_CRAWL_ENABLED = _env_enabled()


def js_crawl_available() -> bool:
    if not _env_enabled():
        return False
    try:
        import playwright  # noqa: F401

        return True
    except Exception:
        return False


def _allow_request(url: str, *, main_host: str | None = None) -> bool:
    """SSRF-gate a Playwright request; fail-closed on third-party hosts.

    ``--host-resolver-rules`` only pins the main document host (see
    ``_chromium_dns_pin_args``), so a fresh Chromium DNS lookup for any other
    host between this check and the actual connect could still rebind. Rather
    than racing that TOCTOU window, block cross-host subresources/navigations
    outright — only the pinned main host is allowed through.
    """
    scheme = (url or "").split(":", 1)[0].lower()
    if scheme in {"data", "blob", "file", "ftp", "ws", "wss"}:
        return False
    if main_host:
        req_host = (urlparse(url).hostname or "").lower().rstrip(".")
        if req_host and req_host != main_host:
            return False
    try:
        assert_public_http_url(url, resolve=True)
        return True
    except UnsafeURLError:
        return False


def _chromium_dns_pin_args(url: str) -> list[str]:
    """Map hostname → first public IP so Chromium cannot rebind mid-request."""
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if not host:
        return []
    try:
        ipaddress.ip_address(host)
        return []  # already a literal IP
    except ValueError:
        pass
    ips = resolve_public_ips(host)
    pinned = ips[0]
    # MAP host to the validated IP; keep localhost/resolv intact.
    return [f"--host-resolver-rules=MAP {host} {pinned}, EXCLUDE localhost"]


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
        launch_args = _chromium_dns_pin_args(safe_url)
    except UnsafeURLError as exc:
        return {
            "ok": False,
            "html": "",
            "error": f"ssrf_blocked:{exc}"[:200],
            "mode": "ssrf_blocked",
        }
    main_host = (urlparse(safe_url).hostname or "").lower().rstrip(".")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=launch_args)
            context = browser.new_context(
                java_script_enabled=True,
                ignore_https_errors=False,
            )
            page = context.new_page()

            def _on_route(route):  # type: ignore[no-untyped-def]
                req_url = route.request.url
                # Block requests that are not public HTTP(S) on the pinned
                # main host — third-party hosts have no DNS pin (see
                # ``_allow_request``) so they fail closed instead of racing
                # a rebind between this check and Chromium's own connect.
                if not _allow_request(req_url, main_host=main_host):
                    return route.abort()
                return route.continue_()

            page.route("**/*", _on_route)
            # Narrow DNS-rebinding TOCTOU: re-resolve + refresh MAP immediately before goto.
            assert_public_http_url(safe_url, resolve=True)
            page.goto(safe_url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Re-validate final URL after redirects (DNS rebinding / open redirect).
            try:
                final = assert_public_http_url(page.url, resolve=True)
                # Reject host swaps after redirect (common rebinding vector).
                if urlparse(safe_url).hostname != urlparse(final).hostname:
                    raise UnsafeURLError("redirect_host_mismatch")
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
