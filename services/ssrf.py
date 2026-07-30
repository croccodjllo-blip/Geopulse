"""SSRF guards for outbound crawl / probe HTTP.

Reject private, loopback, link-local, and cloud metadata targets.
Validate every redirect hop before following.
Pin DNS resolution to a public IP at connect time (mitigate rebinding TOCTOU).
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse, urljoin, urlunparse

import requests
from requests.adapters import HTTPAdapter

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
    """Block non-public targets including CGNAT / shared address space."""
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return True
    if ip.is_multicast or ip.is_unspecified:
        return True
    # IPv4-mapped IPv6
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_blocked_ip(ip.ipv4_mapped)
    # CGNAT / shared (100.64.0.0/10) and other non-global space.
    # Prefer is_global=False over an incomplete private checklist.
    try:
        if not ip.is_global:
            return True
    except Exception:
        return True
    return False


def resolve_public_ips(hostname: str) -> list[str]:
    """Resolve hostname; raise if any address is non-public. Prefer IPv4 order."""
    host = (hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeURLError("Host mancante")
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Host non risolvibile: {host}") from exc
    if not infos:
        raise UnsafeURLError(f"Host non risolvibile: {host}")

    v4: list[str] = []
    v6: list[str] = []
    seen: set[str] = set()
    for info in infos:
        addr = info[4][0]
        if addr in seen:
            continue
        seen.add(addr)
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise UnsafeURLError(f"Host risolve a rete non pubblica ({addr})")
        if isinstance(ip, ipaddress.IPv4Address):
            v4.append(addr)
        else:
            v6.append(addr)
    ordered = v4 + v6
    if not ordered:
        raise UnsafeURLError(f"Host non risolvibile: {host}")
    return ordered


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
    except ValueError:
        # hostname — resolve if requested
        if resolve:
            resolve_public_ips(host)
    else:
        # Do NOT catch UnsafeURLError in the ValueError handler above.
        if _is_blocked_ip(ip):
            raise UnsafeURLError(f"Indirizzo IP non pubblico: {host}")

    # Rebuild without userinfo
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    path = parsed.path or "/"
    cleaned = f"{parsed.scheme}://{netloc}{path}"
    if parsed.query:
        cleaned = f"{cleaned}?{parsed.query}"
    return cleaned


class _HostHeaderSSLAdapter(HTTPAdapter):
    """Verify TLS against the original Host when the URL uses a pinned IP."""

    def send(self, request, **kwargs):  # type: ignore[no-untyped-def]
        host_header = None
        for header in request.headers:
            if header.lower() == "host":
                host_header = request.headers[header]
                break
        pool_kw = self.poolmanager.connection_pool_kw
        if host_header:
            # Strip port for SNI when present (e.g. example.com:443)
            sni = host_header.split(":")[0].strip("[]")
            pool_kw["server_hostname"] = sni
            pool_kw["assert_hostname"] = sni
        else:
            pool_kw.pop("server_hostname", None)
            pool_kw.pop("assert_hostname", None)
        return super().send(request, **kwargs)


def _pin_url_to_ip(url: str, ip: str) -> tuple[str, str]:
    """Rewrite URL netloc to a pinned IP; return (pinned_url, Host header value)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = parsed.port
    host_header = host
    if port:
        host_header = f"{host}:{port}"

    if ":" in ip:
        netloc = f"[{ip}]"
    else:
        netloc = ip
    if port:
        netloc = f"{netloc}:{port}"

    pinned = urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path or "/",
            parsed.params,
            parsed.query,
            "",
        )
    )
    return pinned, host_header


def safe_get(
    session: requests.Session,
    url: str,
    *,
    timeout: float | tuple[float, float],
    max_redirects: int = 5,
    **kwargs,
) -> requests.Response:
    """GET with per-hop SSRF checks and DNS pinning (no private redirect / rebinding)."""
    current = assert_public_http_url(url, resolve=True)
    history: list[requests.Response] = []

    # Dedicated session so we can mount the TLS Host adapter without mutating caller.
    pin_session = requests.Session()
    pin_session.mount("https://", _HostHeaderSSLAdapter())
    # Copy useful defaults from caller session
    pin_session.headers.update(session.headers)
    pin_session.cookies.update(session.cookies)
    if session.proxies:
        pin_session.proxies.update(session.proxies)
    if session.verify is not None:
        pin_session.verify = session.verify

    base_headers = dict(kwargs.pop("headers", {}) or {})

    for _ in range(max_redirects + 1):
        parsed = urlparse(current)
        host = (parsed.hostname or "").lower().rstrip(".")

        # Literal IP vs hostname. UnsafeURLError subclasses ValueError — do not
        # wrap the blocked-IP raise in the same except that catches parse misses.
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ips = resolve_public_ips(host)
            request_url, host_header = _pin_url_to_ip(current, ips[0])
            headers = dict(base_headers)
            headers["Host"] = host_header
        else:
            if _is_blocked_ip(ip):
                raise UnsafeURLError(f"Indirizzo IP non pubblico: {host}")
            request_url = current
            headers = dict(base_headers)

        resp = pin_session.get(
            request_url,
            timeout=timeout,
            allow_redirects=False,
            headers=headers,
            **kwargs,
        )
        # Preserve logical URL for callers (not the pinned IP form).
        resp.url = current  # type: ignore[misc]

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


def safe_post(
    session: requests.Session,
    url: str,
    *,
    data: bytes | None = None,
    json: Any = None,
    timeout: float | tuple[float, float],
    max_redirects: int = 0,
    **kwargs,
) -> requests.Response:
    """POST with SSRF checks and DNS pinning (no private redirect / rebinding).

    Default ``max_redirects=0`` — webhooks must not follow redirects.
    """
    current = assert_public_http_url(url, resolve=True)

    pin_session = requests.Session()
    pin_session.mount("https://", _HostHeaderSSLAdapter())
    pin_session.headers.update(session.headers)
    pin_session.cookies.update(session.cookies)
    if session.proxies:
        pin_session.proxies.update(session.proxies)
    if session.verify is not None:
        pin_session.verify = session.verify

    base_headers = dict(kwargs.pop("headers", {}) or {})
    hops = 0
    while True:
        parsed = urlparse(current)
        host = (parsed.hostname or "").lower().rstrip(".")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ips = resolve_public_ips(host)
            request_url, host_header = _pin_url_to_ip(current, ips[0])
            headers = dict(base_headers)
            headers["Host"] = host_header
        else:
            if _is_blocked_ip(ip):
                raise UnsafeURLError(f"Indirizzo IP non pubblico: {host}")
            request_url = current
            headers = dict(base_headers)

        resp = pin_session.post(
            request_url,
            data=data,
            json=json,
            timeout=timeout,
            allow_redirects=False,
            headers=headers,
            **kwargs,
        )
        resp.url = current  # type: ignore[misc]

        if max_redirects > 0 and (
            resp.is_redirect or resp.status_code in {301, 302, 303, 307, 308}
        ):
            location = resp.headers.get("Location")
            if not location:
                return resp
            hops += 1
            if hops > max_redirects:
                raise UnsafeURLError(f"Troppi redirect (>{max_redirects})")
            nxt = urljoin(current, location)
            current = assert_public_http_url(nxt, resolve=True)
            continue
        return resp
