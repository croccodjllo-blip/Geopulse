"""Add terms consent proof columns on users

Revision ID: 20260811_001
Revises: 20260805_001
Create Date: 2026-08-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_001"
down_revision: Union[str, None] = "20260805_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "users" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "terms_accepted_at" not in cols:
        op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(), nullable=True))
    if "terms_version" not in cols:
        op.add_column("users", sa.Column("terms_version", sa.String(length=40), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "users" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "terms_version" in cols:
        op.drop_column("users", "terms_version")
    if "terms_accepted_at" in cols:
        op.drop_column("users", "terms_accepted_at")
