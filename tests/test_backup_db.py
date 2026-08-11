"""Backup script: URL parsing + SQLite path resolution."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "backup_db", _ROOT / "scripts" / "backup_db.py"
)
assert _SPEC and _SPEC.loader
backup_db = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(backup_db)


def test_parse_postgres_sqlalchemy_url():
    cfg = backup_db._parse_postgres_url(
        "postgresql+psycopg://centropic:s3cret%21@127.0.0.1:5432/centropic"
    )
    assert cfg["user"] == "centropic"
    assert cfg["password"] == "s3cret!"
    assert cfg["host"] == "127.0.0.1"
    assert cfg["port"] == "5432"
    assert cfg["dbname"] == "centropic"


def test_resolve_sqlite_absolute():
    p = backup_db.resolve_sqlite_path(
        "sqlite:////opt/aio-bot/data/database.db", Path("/tmp")
    )
    assert p == Path("/opt/aio-bot/data/database.db")


def test_parse_rejects_sqlite():
    with pytest.raises(SystemExit):
        backup_db._parse_postgres_url("sqlite:////tmp/x.db")
