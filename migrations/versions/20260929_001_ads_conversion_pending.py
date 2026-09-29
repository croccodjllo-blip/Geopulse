"""Pending Ads conversion flags on users (webhook-gated, not thank-you GET).

Revision ID: 20260929_001
Revises: 20260823_001
Create Date: 2026-09-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_001"
down_revision: Union[str, None] = "20260823_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "users" not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "ads_plus_conversion_pending" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "ads_plus_conversion_pending",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if "ads_topup_conversion_pending" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "ads_topup_conversion_pending",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "users" not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "ads_topup_conversion_pending" in cols:
        op.drop_column("users", "ads_topup_conversion_pending")
    if "ads_plus_conversion_pending" in cols:
        op.drop_column("users", "ads_plus_conversion_pending")
