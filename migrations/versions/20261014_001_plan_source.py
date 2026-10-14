"""Stamp complimentary paid plans as plan_source=grant (no downgrade).

Revision ID: 20261014_001
Revises: 20260929_001
Create Date: 2026-10-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261014_001"
down_revision: Union[str, None] = "20260929_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "users" not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "plan_source" not in cols:
        op.add_column("users", sa.Column("plan_source", sa.String(length=20)))
    # Existing paid rows without a Paddle subscription are complimentary
    # grants (admin / stress / demo). Do not change plan.
    op.execute(
        sa.text(
            """
            UPDATE users
            SET plan_source = 'grant'
            WHERE LOWER(COALESCE(plan, '')) IN ('plus', 'pro', 'business')
              AND (paddle_subscription_id IS NULL
                   OR TRIM(paddle_subscription_id) = '')
              AND (plan_source IS NULL OR TRIM(plan_source) = '')
              AND LOWER(COALESCE(plan, '')) <> 'admin'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET plan_source = 'paddle'
            WHERE LOWER(COALESCE(plan, '')) IN ('plus', 'pro', 'business')
              AND paddle_subscription_id IS NOT NULL
              AND TRIM(paddle_subscription_id) <> ''
              AND (plan_source IS NULL OR TRIM(plan_source) = '')
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "users" not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "plan_source" in cols:
        op.drop_column("users", "plan_source")
