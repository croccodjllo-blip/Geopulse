"""Gemini / Google AI citation monitor wiring."""

from __future__ import annotations

from services import citation_monitor as cm


def test_citation_monitor_available_with_gemini(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert cm.citation_monitor_available() is True


def test_probe_gemini_missing_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    out = cm._probe_gemini(["chi è centropic?"], {"centropic"})
    assert out["available"] is False
    assert "GEMINI" in out["reason"]


def test_run_citation_monitor_uses_gemini_engine(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def _fake(**kwargs):
        return {
            "available": True,
            "mention_rate": 50,
            "hits": 1,
            "samples": 2,
            "details": [{"prompt": "p", "mentioned": True, "engine": "google"}],
            "evidence": "measured",
            "model": "gemini-2.0-flash",
        }

    monkeypatch.setattr(cm, "_probe_openai", lambda *a, **k: {"available": False, "details": []})
    monkeypatch.setattr(cm, "_probe_perplexity", lambda *a, **k: {"available": False, "details": []})
    monkeypatch.setattr(cm, "_probe_anthropic", lambda *a, **k: {"available": False, "details": []})
    monkeypatch.setattr(cm, "_probe_gemini", lambda *a, **k: _fake())

    out = cm.run_citation_monitor(brand="Centropic", domain="centropic.ai", prompts=["x"])
    google = next(e for e in out["engines"] if e["id"] == "google")
    assert google["evidence"] == "measured"
    assert google["mention_rate"] == 50
    assert out["available"] is True
