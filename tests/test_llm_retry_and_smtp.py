"""Tests for LLM retry helper and SMTP From alignment."""

from __future__ import annotations

import os

import pytest

from services.llm_retry import call_with_retries, http_should_retry
from services.mailer import smtp_envelope_from


def test_call_with_retries_succeeds_after_rate_limit():
    calls = {"n": 0}

    class RateLimitError(Exception):
        status_code = 429

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RateLimitError("rate limit reached")
        return "ok"

    assert call_with_retries(flaky, retries=5, label="test") == "ok"
    assert calls["n"] == 3


def test_call_with_retries_gives_up():
    class RateLimitError(Exception):
        status_code = 429

    def always():
        raise RateLimitError("still limited")

    with pytest.raises(RateLimitError):
        call_with_retries(always, retries=2, label="test")


def test_http_should_retry():
    assert http_should_retry(429) is True
    assert http_should_retry(503) is True
    assert http_should_retry(400) is False


def test_smtp_envelope_rewrites_mismatched_from(monkeypatch):
    monkeypatch.setenv("MAIL_FROM", "Centropic <noreply@centropic.ai>")
    monkeypatch.setenv("SMTP_USER", "noreply@geopulse.it")
    assert smtp_envelope_from() == "Centropic <noreply@geopulse.it>"


def test_smtp_envelope_keeps_matching_from(monkeypatch):
    monkeypatch.setenv("MAIL_FROM", "Centropic <noreply@geopulse.it>")
    monkeypatch.setenv("SMTP_USER", "noreply@geopulse.it")
    assert smtp_envelope_from() == "Centropic <noreply@geopulse.it>"


def test_smtp_envelope_without_smtp_user(monkeypatch):
    monkeypatch.setenv("MAIL_FROM", "Centropic <noreply@centropic.ai>")
    monkeypatch.delenv("SMTP_USER", raising=False)
    assert smtp_envelope_from() == "Centropic <noreply@centropic.ai>"
