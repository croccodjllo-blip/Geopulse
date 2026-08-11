"""kick_analyze_worker must prefer an out-of-process worker."""

from __future__ import annotations

from unittest.mock import MagicMock


def test_kick_analyze_worker_spawns_detached_process(monkeypatch, tmp_path):
    import app as app_mod

    app_py = tmp_path / "app.py"
    app_py.write_text("# stub\n", encoding="utf-8")
    worker = tmp_path / "scripts" / "analyze_worker.py"
    worker.parent.mkdir(parents=True, exist_ok=True)
    worker.write_text("# stub\n", encoding="utf-8")
    monkeypatch.setattr(app_mod, "__file__", str(app_py))

    calls: list[dict] = []

    def fake_popen(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return MagicMock(pid=4242, wait=MagicMock(return_value=0))

    monkeypatch.setattr(app_mod.subprocess, "Popen", fake_popen)

    started_names: list[str | None] = []

    class FakeThread:
        def __init__(self, target=None, daemon=None, name=None):
            self.target = target
            self.daemon = daemon
            self.name = name

        def start(self):
            started_names.append(self.name)

    monkeypatch.setattr(app_mod.threading, "Thread", FakeThread)

    app_mod.kick_analyze_worker()

    assert len(calls) == 1
    popen_args = calls[0]["args"][0]
    assert popen_args[0] == app_mod.sys.executable
    assert str(popen_args[1]).endswith("analyze_worker.py")
    assert popen_args[2:] == ["--limit", "1"]
    assert calls[0]["kwargs"]["start_new_session"] is True
    assert any(n and str(n).startswith("analyze-kick-reap-") for n in started_names)
    assert "analyze-kick" not in started_names


def test_kick_analyze_worker_falls_back_to_thread(monkeypatch, tmp_path):
    import app as app_mod

    app_py = tmp_path / "app.py"
    app_py.write_text("# stub\n", encoding="utf-8")
    worker = tmp_path / "scripts" / "analyze_worker.py"
    worker.parent.mkdir(parents=True, exist_ok=True)
    worker.write_text("# stub\n", encoding="utf-8")
    monkeypatch.setattr(app_mod, "__file__", str(app_py))

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
