"""xAI Grok citation monitor wiring."""

from __future__ import annotations

from services import citation_monitor as cm


def test_citation_monitor_available_with_xai(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("XAI_API_KEY", "test-xai-key")
    assert cm.citation_monitor_available() is True


def test_probe_xai_missing_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    out = cm._probe_xai(["chi è centropic?"], {"centropic"})
    assert out["available"] is False
    assert "XAI" in out["reason"] or "GROK" in out["reason"]


def test_run_citation_monitor_uses_grok_engine(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("XAI_API_KEY", "test-xai-key")

    def _fake(*a, **k):
        return {
            "available": True,
            "mention_rate": 40,
            "hits": 1,
            "samples": 2,
            "details": [{"prompt": "p", "mentioned": True, "engine": "xai"}],
            "evidence": "measured",
            "model": "grok-4-1-fast-non-reasoning",
        }

    monkeypatch.setattr(cm, "_probe_openai", lambda *a, **k: {"available": False, "details": []})
    monkeypatch.setattr(cm, "_probe_perplexity", lambda *a, **k: {"available": False, "details": []})
    monkeypatch.setattr(cm, "_probe_anthropic", lambda *a, **k: {"available": False, "details": []})
    monkeypatch.setattr(cm, "_probe_gemini", lambda *a, **k: {"available": False, "details": []})
    monkeypatch.setattr(cm, "_probe_xai", _fake)

    out = cm.run_citation_monitor(brand="Centropic", domain="centropic.ai", prompts=["x"])
    grok = next(e for e in out["engines"] if e["id"] == "xai")
    assert grok["label"] == "Grok"
    assert grok["evidence"] == "measured"
    assert grok["mention_rate"] == 40
    assert out["available"] is True
