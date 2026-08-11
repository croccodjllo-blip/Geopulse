"""Sentry bootstrap helpers."""

from __future__ import annotations

from centropic.sentry_setup import (
    _traces_sampler,
    init_sentry,
    sentry_dsn,
    sentry_environment,
    sentry_release,
)


def test_sentry_environment_defaults(monkeypatch):
    monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
    monkeypatch.setenv("FLASK_DEBUG", "0")
    assert sentry_environment() == "production"
    monkeypatch.setenv("FLASK_DEBUG", "1")
    assert sentry_environment() == "development"
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")
    assert sentry_environment() == "staging"


def test_traces_sampler_drops_health(monkeypatch):
    monkeypatch.setenv("SENTRY_TRACES", "0.2")
    assert (
        _traces_sampler({"wsgi_environ": {"PATH_INFO": "/health"}}) == 0.0
    )
    assert (
        _traces_sampler({"wsgi_environ": {"PATH_INFO": "/static/css/app.css"}}) == 0.0
    )
    assert _traces_sampler({"wsgi_environ": {"PATH_INFO": "/dashboard"}}) == 0.2


def test_init_sentry_noop_without_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert sentry_dsn() == ""
    assert init_sentry(None) is False


def test_sentry_release_from_git_sha(monkeypatch):
    monkeypatch.delenv("SENTRY_RELEASE", raising=False)
    monkeypatch.setenv("GIT_SHA", "abc123")
    assert sentry_release() == "abc123"
