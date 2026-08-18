"""Add Google Search Console OAuth token columns on users

Revision ID: 20260818_001
Revises: 20260812_001
Create Date: 2026-08-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_001"
down_revision: Union[str, None] = "20260812_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "users" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    adds = [
        ("gsc_refresh_token", sa.Text(), True),
        ("gsc_access_token", sa.Text(), True),
        ("gsc_token_expires_at", sa.DateTime(), True),
        ("gsc_account_email", sa.String(length=255), True),
        ("gsc_connected_at", sa.DateTime(), True),
        (
            "gsc_site_urls_json",
            sa.Text(),
            False,
        ),
    ]
    for name, col, nullable in adds:
        if name in cols:
            continue
        kwargs: dict = {"nullable": nullable}
        if name == "gsc_site_urls_json":
            op.add_column(
                "users",
                sa.Column(name, col, nullable=False, server_default=""),
            )
        else:
            op.add_column("users", sa.Column(name, col, **kwargs))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "users" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    for name in (
        "gsc_site_urls_json",
        "gsc_connected_at",
        "gsc_account_email",
        "gsc_token_expires_at",
        "gsc_access_token",
        "gsc_refresh_token",
    ):
        if name in cols:
            op.drop_column("users", name)
