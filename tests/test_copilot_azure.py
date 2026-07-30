"""Azure AI Foundry Copilot probe wiring."""

from __future__ import annotations

from services import citation_monitor as cm


def test_azure_configured_requires_endpoint(monkeypatch):
    monkeypatch.delenv("AZURE_AI_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_AI_ENDPOINT", raising=False)
    assert cm._azure_configured() is False


def test_azure_configured_with_sp(monkeypatch):
    monkeypatch.setenv(
        "AZURE_AI_PROJECT_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/demo",
    )
    monkeypatch.setenv("AZURE_TENANT_ID", "tid")
    monkeypatch.setenv("AZURE_CLIENT_ID", "cid")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "sec")
    assert cm._azure_configured() is True
    assert cm.citation_monitor_available() is True


def test_probe_copilot_missing_endpoint(monkeypatch):
    monkeypatch.delenv("AZURE_AI_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_AI_ENDPOINT", raising=False)
    out = cm._probe_copilot(["chi è centropic?"], {"centropic"})
    assert out["available"] is False
    assert "ENDPOINT" in out["reason"].upper() or "endpoint" in out["reason"].lower()


def test_run_citation_monitor_uses_copilot_engine(monkeypatch):
    monkeypatch.setenv(
        "AZURE_AI_PROJECT_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/demo",
    )
    monkeypatch.setenv("AZURE_TENANT_ID", "tid")
    monkeypatch.setenv("AZURE_CLIENT_ID", "cid")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "sec")

    def _fake(*a, **k):
        return {
            "available": True,
            "mention_rate": 33,
            "hits": 1,
            "samples": 3,
            "details": [{"prompt": "p", "mentioned": True, "engine": "bing"}],
            "evidence": "measured",
            "model": "gpt-4o-mini",
        }

    monkeypatch.setattr(cm, "_probe_openai", lambda *a, **k: {"available": False, "details": []})
    monkeypatch.setattr(cm, "_probe_perplexity", lambda *a, **k: {"available": False, "details": []})
    monkeypatch.setattr(cm, "_probe_anthropic", lambda *a, **k: {"available": False, "details": []})
    monkeypatch.setattr(cm, "_probe_gemini", lambda *a, **k: {"available": False, "details": []})
    monkeypatch.setattr(cm, "_probe_xai", lambda *a, **k: {"available": False, "details": []})
    monkeypatch.setattr(cm, "_probe_copilot", _fake)

    out = cm.run_citation_monitor(brand="Centropic", domain="centropic.ai", prompts=["x"])
    bing = next(e for e in out["engines"] if e["id"] == "bing")
    assert bing["label"] == "Copilot"
    assert bing["evidence"] == "measured"
    assert bing["mention_rate"] == 33
