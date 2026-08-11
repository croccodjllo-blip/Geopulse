"""Regression: BEGIN IMMEDIATE must not poison Postgres transactions."""

from __future__ import annotations

from unittest.mock import MagicMock

from services.jobs import _begin_immediate as jobs_begin
from services.usage_billing import _begin_immediate as billing_begin


def test_jobs_begin_immediate_skips_postgres():
    session = MagicMock()
    bind = MagicMock()
    bind.dialect.name = "postgresql"
    session.get_bind.return_value = bind
    jobs_begin(session)
    session.execute.assert_not_called()


def test_jobs_begin_immediate_runs_on_sqlite():
    session = MagicMock()
    bind = MagicMock()
    bind.dialect.name = "sqlite"
    session.get_bind.return_value = bind
    jobs_begin(session)
    session.execute.assert_called_once()
    sql = str(session.execute.call_args[0][0])
    assert "BEGIN IMMEDIATE" in sql


def test_billing_begin_immediate_skips_postgres():
    session = MagicMock()
    bind = MagicMock()
    bind.dialect.name = "postgresql"
    session.get_bind.return_value = bind
    billing_begin(session)
    session.execute.assert_not_called()
