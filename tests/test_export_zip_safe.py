"""ZIP folder names must not allow path traversal."""

from __future__ import annotations

from types import SimpleNamespace

from services.export import _safe_zip_folder, multi_site_zip


def test_safe_zip_folder_strips_traversal():
    assert ".." not in _safe_zip_folder("../../etc/passwd")
    assert "/" not in _safe_zip_folder("a/b/c")
    assert "\\" not in _safe_zip_folder("a\\b")
    assert _safe_zip_folder("evil.com/../../x") == "x" or ".." not in _safe_zip_folder(
        "evil.com/../../x"
    )


def test_multi_site_zip_uses_safe_folders(monkeypatch):
    monkeypatch.setattr(
        "services.export.pack_fix_html_bytes",
        lambda site: b"<html>ok</html>",
    )
    site = SimpleNamespace(id=1, domain="../../evil")
    raw = multi_site_zip([site])
    assert b"../" not in raw
    assert b"evil" in raw or b"site-1" in raw or b"fix.html" in raw
