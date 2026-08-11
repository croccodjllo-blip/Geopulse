"""Add guest_previews table for PLG hero URL funnel

Revision ID: 20260811_002
Revises: 20260811_001
Create Date: 2026-08-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_002"
down_revision: Union[str, None] = "20260811_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "guest_previews" in tables:
        return
    op.create_table(
        "guest_previews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(length=48), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("aio_score", sa.Integer(), nullable=True),
        sa.Column("geo_score", sa.Integer(), nullable=True),
        sa.Column("findings_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("pack_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("claimed_user_id", sa.Integer(), nullable=True),
        sa.Column("claimed_site_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["claimed_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["claimed_site_id"], ["site_analyses.id"]),
    )
    op.create_index("ix_guest_previews_token", "guest_previews", ["token"], unique=True)
    op.create_index("ix_guest_previews_status", "guest_previews", ["status"])
    op.create_index("ix_guest_previews_ip_hash", "guest_previews", ["ip_hash"])
    op.create_index("ix_guest_previews_created_at", "guest_previews", ["created_at"])
    op.create_index("ix_guest_previews_expires_at", "guest_previews", ["expires_at"])
    op.create_index("ix_guest_previews_claimed_user_id", "guest_previews", ["claimed_user_id"])
    op.create_index("ix_guest_previews_claimed_site_id", "guest_previews", ["claimed_site_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "guest_previews" not in set(insp.get_table_names()):
        return
    op.drop_table("guest_previews")
