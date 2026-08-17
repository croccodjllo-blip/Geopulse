"""Content-Security-Policy helpers with per-request nonces."""

from __future__ import annotations

import secrets
from typing import Any

from flask import Flask, g, request


def new_csp_nonce() -> str:
    return secrets.token_urlsafe(16)


def configure_csp(app: Flask) -> None:
    @app.before_request
    def _bind_csp_nonce() -> None:
        g.csp_nonce = new_csp_nonce()


def build_csp_header(
    *,
    nonce: str,
    paddle: bool,
    analytics: bool,
    adsense: bool,
) -> str:
    """Prefer nonce-based script-src; keep strict-dynamic for modern browsers.

    Styles: CSP3 ``style-src-elem`` requires nonce/'self'. No ``style-src-attr``
    allowlist by default — templates must not use HTML ``style=``.
    When Paddle overlay is enabled we relax ``style-src-attr`` and allow
    Paddle CDN styles: Billing checkout injects inline style attrs / CSS that
    otherwise leave an invisible/broken overlay under ``style-src-attr 'none'``.
    """
    script_src = [
        "'self'",
        f"'nonce-{nonce}'",
        "'strict-dynamic'",
    ]
    style_src = [
        "'self'",
        f"'nonce-{nonce}'",
        "https://fonts.googleapis.com",
    ]
    style_src_elem = list(style_src)
    style_src_attr = "'none'"
    img_src = ["'self'", "data:"]
    connect_src = ["'self'"]
    frame_src = ["'self'"]
    font_src = ["'self'", "https://fonts.gstatic.com", "data:"]

    if paddle:
        script_src.append("https://cdn.paddle.com")
        style_src.append("https://cdn.paddle.com")
        style_src_elem.append("https://cdn.paddle.com")
        # Overlay chrome uses inline style attributes.
        style_src_attr = "'unsafe-inline'"
        connect_src.extend(
            [
                "https://api.paddle.com",
                "https://sandbox-api.paddle.com",
                "https://checkout.paddle.com",
                "https://sandbox-checkout.paddle.com",
                "https://checkout-service.paddle.com",
                "https://sandbox-checkout-service.paddle.com",
                "https://buy.paddle.com",
                "https://sandbox-buy.paddle.com",
                "https://cdn.paddle.com",
            ]
        )
        frame_src.extend(
            [
                "https://checkout.paddle.com",
                "https://sandbox-checkout.paddle.com",
                "https://buy.paddle.com",
                "https://sandbox-buy.paddle.com",
                "https://cdn.paddle.com",
            ]
        )
    if analytics:
        script_src.extend(
            ["https://www.googletagmanager.com", "https://www.google-analytics.com"]
        )
        connect_src.extend(
            [
                "https://www.google-analytics.com",
                "https://region1.google-analytics.com",
                "https://www.google.com",
                "https://googleads.g.doubleclick.net",
            ]
        )
        img_src.extend(["https://www.google-analytics.com", "https://www.google.com"])
    if adsense:
        script_src.extend(
            [
                "https://pagead2.googlesyndication.com",
                "https://partner.googleadservices.com",
                "https://www.googleadservices.com",
            ]
        )
        img_src.extend(
            [
                "https://googleads.g.doubleclick.net",
                "https://pagead2.googlesyndication.com",
                "https://www.googleadservices.com",
            ]
        )
        frame_src.extend(
            [
                "https://googleads.g.doubleclick.net",
                "https://tpc.googlesyndication.com",
                "https://www.google.com",
            ]
        )

    def uniq(items: list[str]) -> str:
        return " ".join(dict.fromkeys(items))

    return (
        "default-src 'self'; "
        f"script-src {uniq(script_src)}; "
        f"style-src {uniq(style_src)}; "
        f"style-src-elem {uniq(style_src_elem)}; "
        f"style-src-attr {style_src_attr}; "
        f"font-src {uniq(font_src)}; "
        f"img-src {uniq(img_src)}; "
        f"connect-src {uniq(connect_src)}; "
        f"frame-src {uniq(frame_src)}; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )


def inject_csp_context() -> dict[str, Any]:
    return {"csp_nonce": getattr(g, "csp_nonce", "")}
