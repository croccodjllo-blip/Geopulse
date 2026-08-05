"""Baseline: organization tenancy + site.organization_id

Revision ID: 20260805_001
Revises:
Create Date: 2026-08-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "organizations" not in tables:
        op.create_table(
            "organizations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("plan", sa.String(length=40), nullable=False, server_default="business"),
            sa.Column("agency_brand_json", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
        op.create_index("ix_organizations_owner_user_id", "organizations", ["owner_user_id"])

    if "organization_members" not in tables:
        op.create_table(
            "organization_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id"),
                nullable=False,
            ),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
        )
        op.create_index(
            "ix_organization_members_organization_id",
            "organization_members",
            ["organization_id"],
        )
        op.create_index(
            "ix_organization_members_user_id", "organization_members", ["user_id"]
        )

    if "site_analyses" in tables:
        cols = {c["name"] for c in insp.get_columns("site_analyses")}
        if "organization_id" not in cols:
            op.add_column(
                "site_analyses",
                sa.Column("organization_id", sa.Integer(), nullable=True),
            )
            # FK best-effort (SQLite may ignore)
            try:
                op.create_foreign_key(
                    "fk_site_analyses_organization_id",
                    "site_analyses",
                    "organizations",
                    ["organization_id"],
                    ["id"],
                )
            except Exception:
                pass
            try:
                op.create_index(
                    "ix_site_analyses_organization_id",
                    "site_analyses",
                    ["organization_id"],
                )
            except Exception:
                pass


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "site_analyses" in tables:
        cols = {c["name"] for c in insp.get_columns("site_analyses")}
        if "organization_id" in cols:
            try:
                op.drop_constraint(
                    "fk_site_analyses_organization_id", "site_analyses", type_="foreignkey"
                )
            except Exception:
                pass
            op.drop_column("site_analyses", "organization_id")
    if "organization_members" in tables:
        op.drop_table("organization_members")
    if "organizations" in tables:
        op.drop_table("organizations")
