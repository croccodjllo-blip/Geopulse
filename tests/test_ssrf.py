from __future__ import annotations

import pytest

from services.ssrf import UnsafeURLError, assert_public_http_url


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
