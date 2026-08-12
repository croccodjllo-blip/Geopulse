"""Add pack_uri for optional S3 analysis artifact offload

Revision ID: 20260812_001
Revises: 20260811_002
Create Date: 2026-08-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_001"
down_revision: Union[str, None] = "20260811_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "site_analyses" in tables:
        cols = {c["name"] for c in insp.get_columns("site_analyses")}
        if "pack_uri" not in cols:
            op.add_column(
                "site_analyses",
                sa.Column(
                    "pack_uri",
                    sa.String(length=500),
                    nullable=False,
                    server_default="",
                ),
            )

    if "analysis_runs" in tables:
        cols = {c["name"] for c in insp.get_columns("analysis_runs")}
        if "pack_uri" not in cols:
            op.add_column(
                "analysis_runs",
                sa.Column(
                    "pack_uri",
                    sa.String(length=500),
                    nullable=False,
                    server_default="",
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "analysis_runs" in tables:
        cols = {c["name"] for c in insp.get_columns("analysis_runs")}
        if "pack_uri" in cols:
            op.drop_column("analysis_runs", "pack_uri")
    if "site_analyses" in tables:
        cols = {c["name"] for c in insp.get_columns("site_analyses")}
        if "pack_uri" in cols:
            op.drop_column("site_analyses", "pack_uri")
