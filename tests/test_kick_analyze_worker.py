"""kick_analyze_worker must prefer an out-of-process worker."""

from __future__ import annotations

from unittest.mock import MagicMock


def test_kick_analyze_worker_spawns_detached_process(monkeypatch):
    import app as app_mod

    calls: list[dict] = []

    def fake_popen(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return MagicMock(pid=4242)

    monkeypatch.setattr(app_mod.subprocess, "Popen", fake_popen)
    # Ensure thread fallback is not used when Popen succeeds.
    started = []
    monkeypatch.setattr(
        app_mod.threading,
        "Thread",
        lambda *a, **k: started.append((a, k)) or MagicMock(start=lambda: None),
    )

    app_mod.kick_analyze_worker()

    assert len(calls) == 1
    popen_args = calls[0]["args"][0]
    assert popen_args[0] == app_mod.sys.executable
    assert popen_args[1].endswith("scripts/analyze_worker.py")
    assert popen_args[2:] == ["--limit", "1"]
    assert calls[0]["kwargs"]["start_new_session"] is True
    assert started == []


def test_kick_analyze_worker_falls_back_to_thread(monkeypatch):
    import app as app_mod

    monkeypatch.setattr(
        app_mod.subprocess,
        "Popen",
        lambda *a, **k: (_ for _ in ()).throw(OSError("nope")),
    )
    started = []

    class FakeThread:
        def __init__(self, target=None, daemon=None, name=None):
            self.target = target
            self.daemon = daemon
            self.name = name

        def start(self):
            started.append(self)

    monkeypatch.setattr(app_mod.threading, "Thread", FakeThread)
    app_mod.kick_analyze_worker()
    assert len(started) == 1
    assert started[0].daemon is True
    assert started[0].name == "analyze-kick"
