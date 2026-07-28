from __future__ import annotations

import pytest

from services.ssrf import (
    UnsafeURLError,
    assert_public_http_url,
    resolve_public_ips,
    _pin_url_to_ip,
)


def test_rejects_loopback():
    with pytest.raises(UnsafeURLError):
        assert_public_http_url("http://127.0.0.1/")


def test_rejects_metadata_hostname():
    with pytest.raises(UnsafeURLError):
        assert_public_http_url("http://metadata.google.internal/")


def test_rejects_private_literal():
    with pytest.raises(UnsafeURLError):
        assert_public_http_url("http://10.0.0.5/hook")


def test_rejects_credentials_in_url():
    with pytest.raises(UnsafeURLError):
        assert_public_http_url("https://user:pass@example.com/")


def test_accepts_public_https():
    # resolve=False evita dipendenza DNS in CI
    out = assert_public_http_url("https://example.com/path", resolve=False)
    assert out.startswith("https://example.com/")


def test_resolve_public_ips_rejects_private(monkeypatch):
    def fake_getaddrinfo(host, *args, **kwargs):
        return [(0, 0, 0, "", ("10.0.0.1", 0))]

    monkeypatch.setattr("services.ssrf.socket.getaddrinfo", fake_getaddrinfo)
    with pytest.raises(UnsafeURLError, match="non pubblica"):
        resolve_public_ips("evil.example")


def test_resolve_public_ips_prefers_ipv4(monkeypatch):
    def fake_getaddrinfo(host, *args, **kwargs):
        return [
            (0, 0, 0, "", ("2606:4700:4700::1111", 0)),
            (0, 0, 0, "", ("93.184.216.34", 0)),
        ]

    monkeypatch.setattr("services.ssrf.socket.getaddrinfo", fake_getaddrinfo)
    assert resolve_public_ips("example.com")[0] == "93.184.216.34"


def test_pin_url_to_ip():
    pinned, host = _pin_url_to_ip("https://example.com/a?q=1", "93.184.216.34")
    assert pinned == "https://93.184.216.34/a?q=1"
    assert host == "example.com"

    pinned6, host6 = _pin_url_to_ip("https://example.com:8443/", "2606:4700:4700::1111")
    assert pinned6 == "https://[2606:4700:4700::1111]:8443/"
    assert host6 == "example.com:8443"
