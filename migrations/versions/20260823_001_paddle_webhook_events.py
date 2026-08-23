"""Durable unique store for Paddle webhook event ids

Revision ID: 20260823_001
Revises: 20260818_001
Create Date: 2026-08-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260823_001"
down_revision: Union[str, None] = "20260818_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "paddle_webhook_events" in tables:
        return
    op.create_table(
        "paddle_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=190), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_paddle_webhook_events_event_id",
        "paddle_webhook_events",
        ["event_id"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "paddle_webhook_events" not in set(insp.get_table_names()):
        return
    op.drop_index("ix_paddle_webhook_events_event_id", table_name="paddle_webhook_events")
    op.drop_table("paddle_webhook_events")
