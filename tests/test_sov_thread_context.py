"""SoV parallel probes must not poison Flask/SQLAlchemy sessions."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest


def test_usage_callback_errors_do_not_abort_monitor(monkeypatch):
    """Non-credit usage failures are swallowed; monitor still returns engines."""
    import services.citation_monitor as cm

    monkeypatch.setattr(cm, "_sov_engine_parallelism", lambda: 2)
    monkeypatch.setattr(cm, "_sov_prompt_limit", lambda: 1)

    calls = {"n": 0}

    def boom(**kwargs):
        calls["n"] += 1
        raise RuntimeError("Working outside of application context.")

    def fake_probe(prompts, needles, usage_callback=None):
        if usage_callback:
            usage_callback(
                provider="openai", model="x", input_tokens=1, output_tokens=1
            )
        return {
            "available": True,
            "mention_rate": 50,
            "hits": 1,
            "samples": 1,
            "details": [],
            "evidence": "measured",
        }

    monkeypatch.setattr(cm, "_probe_openai", fake_probe)
    monkeypatch.setattr(cm, "_probe_perplexity", lambda *a, **k: {"available": False, "reason": "skip"})
    monkeypatch.setattr(cm, "_probe_anthropic", lambda *a, **k: {"available": False, "reason": "skip"})
    monkeypatch.setattr(cm, "_probe_gemini", lambda *a, **k: {"available": False, "reason": "skip"})
    monkeypatch.setattr(cm, "_probe_xai", lambda *a, **k: {"available": False, "reason": "skip"})
    monkeypatch.setattr(cm, "_probe_copilot", lambda *a, **k: {"available": False, "reason": "skip"})

    out = cm.run_citation_monitor(
        brand="Centropic",
        domain="centropic.ai",
        prompts=["Chi è Centropic?"],
        usage_callback=boom,
    )
    assert calls["n"] >= 1
    assert out.get("available") is True or any(
        e.get("id") == "openai" for e in (out.get("engines") or [])
    )


def test_insufficient_credit_aborts_monitor(monkeypatch):
    import services.citation_monitor as cm
    from services.usage_billing import InsufficientCreditError

    monkeypatch.setattr(cm, "_sov_engine_parallelism", lambda: 2)
    monkeypatch.setattr(cm, "_sov_prompt_limit", lambda: 1)

    def no_credit(**kwargs):
        raise InsufficientCreditError("saldo esaurito")

    def fake_probe(prompts, needles, usage_callback=None):
        if usage_callback:
            usage_callback(
                provider="openai", model="x", input_tokens=10, output_tokens=10
            )
        return {"available": True, "mention_rate": 10, "hits": 0, "samples": 1, "details": []}

    monkeypatch.setattr(cm, "_probe_openai", fake_probe)
    monkeypatch.setattr(cm, "_probe_perplexity", fake_probe)
    monkeypatch.setattr(cm, "_probe_anthropic", lambda *a, **k: {"available": False, "reason": "skip"})
    monkeypatch.setattr(cm, "_probe_gemini", lambda *a, **k: {"available": False, "reason": "skip"})
    monkeypatch.setattr(cm, "_probe_xai", lambda *a, **k: {"available": False, "reason": "skip"})
    monkeypatch.setattr(cm, "_probe_copilot", lambda *a, **k: {"available": False, "reason": "skip"})

    with pytest.raises(InsufficientCreditError):
        cm.run_citation_monitor(
            brand="Centropic",
            domain="centropic.ai",
            prompts=["test"],
            usage_callback=no_credit,
        )


def test_app_context_wrapper_works_from_thread():
    """Mimic job usage cb: open app context inside thread before touching db proxy."""
    from flask import Flask, has_app_context

    app = Flask("ctx-test")
    seen = {"ok": False}

    def cb():
        with app.app_context():
            seen["ok"] = has_app_context()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(cb).result(timeout=5)
    assert seen["ok"] is True
