"""SSRF guards for outbound crawl / probe HTTP.

Reject private, loopback, link-local, and cloud metadata targets.
Validate every redirect hop before following.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse, urljoin

import requests

# Hostnames commonly used for cloud metadata (resolve to link-local)
_BLOCKED_HOSTNAMES = frozenset(
    {
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
    }
)


class UnsafeURLError(ValueError):
    """URL non consentito per crawl (SSRF)."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return True
    if ip.is_multicast or ip.is_unspecified:
        return True
    # IPv4-mapped IPv6
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_blocked_ip(ip.ipv4_mapped)
    # AWS/GCP/Azure metadata commonly 169.254.169.254 (link-local — already covered)
    return False


def assert_public_http_url(url: str, *, resolve: bool = True) -> str:
    """Raise UnsafeURLError if URL is not a safe public http(s) target.

    Returns a cleaned URL string (credentials stripped from netloc).
    """
    raw = (url or "").strip()
    if not raw:
        raise UnsafeURLError("URL vuoto")

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURLError("Solo http/https consentiti")
    if not parsed.hostname:
        raise UnsafeURLError("Host mancante")
    if parsed.username or parsed.password:
        raise UnsafeURLError("Credenziali nell’URL non consentite")

    host = parsed.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTNAMES or host.endswith(".internal"):
        raise UnsafeURLError(f"Host non consentito: {host}")

    # Literal IP in hostname
    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked_ip(ip):
            raise UnsafeURLError(f"Indirizzo IP non pubblico: {host}")
    except ValueError:
        # hostname — resolve if requested
        if resolve:
            try:
                infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            except socket.gaierror as exc:
                raise UnsafeURLError(f"Host non risolvibile: {host}") from exc
            if not infos:
                raise UnsafeURLError(f"Host non risolvibile: {host}")
            for info in infos:
                addr = info[4][0]
                try:
                    ip = ipaddress.ip_address(addr)
                except ValueError:
                    continue
                if _is_blocked_ip(ip):
                    raise UnsafeURLError(
                        f"Host risolve a rete non pubblica ({addr})"
                    )

    # Rebuild without userinfo
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    path = parsed.path or "/"
    cleaned = f"{parsed.scheme}://{netloc}{path}"
    if parsed.query:
        cleaned = f"{cleaned}?{parsed.query}"
    return cleaned


def safe_get(
    session: requests.Session,
    url: str,
    *,
    timeout: float | tuple[float, float],
    max_redirects: int = 5,
    **kwargs,
) -> requests.Response:
    """GET with per-hop SSRF checks (no automatic cross-host private redirect)."""
    current = assert_public_http_url(url, resolve=True)
    history: list[requests.Response] = []

    for _ in range(max_redirects + 1):
        resp = session.get(
            current,
            timeout=timeout,
            allow_redirects=False,
            **kwargs,
        )
        if resp.is_redirect or resp.status_code in {301, 302, 303, 307, 308}:
            location = resp.headers.get("Location")
            if not location:
                resp.raise_for_status()
                return resp
            nxt = urljoin(current, location)
            try:
                nxt = assert_public_http_url(nxt, resolve=True)
            except UnsafeURLError as exc:
                raise UnsafeURLError(
                    f"Redirect verso destinazione non consentita: {exc}"
                ) from exc
            history.append(resp)
            current = nxt
            continue

        # Attach synthetic history for callers that inspect .history / .url
        resp.history = history  # type: ignore[misc]
        return resp

    raise UnsafeURLError(f"Troppi redirect (>{max_redirects})")
