"""Competitor snapshot auto-fill flash is native gettext (not raw Italian)."""

from __future__ import annotations

import os

os.environ.setdefault("FLASK_DEBUG", "1")
os.environ.setdefault("FLASK_SECRET_KEY", "test-comp-flash-i18n")

from flask_babel import force_locale, gettext as _

from app import app

MSGID = "Competitor snapshot compilato in automatico: %(hosts)s"


def test_competitor_snapshot_flash_native():
    with app.app_context():
        with force_locale("en"):
            got = _(MSGID) % {"hosts": "surferseo.com, peec.ai"}
            assert got == "Competitor snapshot auto-filled: surferseo.com, peec.ai"
            assert "compilato" not in got
        with force_locale("de"):
            got = _(MSGID) % {"hosts": "peec.ai"}
            assert "automatisch" in got.lower() or "Snapshot" in got
            assert "compilato" not in got
        with force_locale("es"):
            assert "compilato" not in _(MSGID) % {"hosts": "x.com"}
        with force_locale("ko"):
            assert "compilato" not in _(MSGID) % {"hosts": "x.com"}
        with force_locale("zh_Hans"):
            assert "compilato" not in _(MSGID) % {"hosts": "x.com"}
