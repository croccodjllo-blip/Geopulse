"""Organization multi-tenancy for Business / agency workspaces."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import UniqueConstraint

from centropic.extensions import db

ORG_ROLES = frozenset({"owner", "admin", "member", "viewer"})
WRITE_ROLES = frozenset({"owner", "admin", "member"})


def resolve_existing_site_for_analyze(model: Any, user: Any, url: str) -> Any | None:
    """Owned site first, then org-shared. Callers must enforce write ACL."""
    existing = model.query.filter_by(user_id=user.id, url=url).first()
    if existing is not None:
        return existing
    return sites_query_for_user(model, user).filter_by(url=url).first()


def assert_can_remesure_site(user: Any, site: Any) -> bool:
    """True when ``site`` is None (new) or the user may write it."""
    if site is None:
        return True
    return user_can_write_site(user, site)


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "workspace").lower()).strip("-") or "workspace"
    return f"{base[:48]}-{secrets.token_hex(3)}"


class Organization(db.Model):
    """Agency / team workspace. Business plan owns at least one org."""

    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    owner_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    plan = db.Column(db.String(40), nullable=False, default="business")
    agency_brand_json = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    members = db.relationship(
        "OrganizationMember",
        back_populates="organization",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )


class OrganizationMember(db.Model):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default="member")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    organization = db.relationship("Organization", back_populates="members")


def ensure_personal_org(user: Any) -> Organization | None:
    """For Business/Admin users, ensure a default workspace exists."""
    if user is None:
        return None
    if not (getattr(user, "is_business", False) or getattr(user, "is_admin", False)):
        return None
    existing = (
        Organization.query.filter_by(owner_user_id=user.id)
        .order_by(Organization.id.asc())
        .first()
    )
    if existing:
        return existing
    org = Organization(
        name=f"{getattr(user, 'company', None) or getattr(user, 'name', 'Workspace')}",
        slug=_slugify(getattr(user, "company", None) or getattr(user, "name", "ws")),
        owner_user_id=user.id,
        plan="business" if getattr(user, "is_business", False) else "admin",
        agency_brand_json=getattr(user, "agency_brand_json", "") or "",
    )
    db.session.add(org)
    db.session.flush()
    db.session.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
        )
    )
    return org


def membership_for(user_id: int, org_id: int) -> OrganizationMember | None:
    return OrganizationMember.query.filter_by(
        user_id=user_id, organization_id=org_id
    ).first()


def user_org_ids(user_id: int) -> list[int]:
    rows = (
        OrganizationMember.query.filter_by(user_id=user_id)
        .with_entities(OrganizationMember.organization_id)
        .all()
    )
    return [r[0] for r in rows]


def user_can_access_site(user: Any, site: Any) -> bool:
    """Owner always; org members if site is attached to a shared workspace."""
    if user is None or site is None:
        return False
    if getattr(site, "user_id", None) == getattr(user, "id", None):
        return True
    org_id = getattr(site, "organization_id", None)
    if not org_id:
        return False
    return membership_for(user.id, org_id) is not None


def get_accessible_site(model: Any, user: Any, site_id: int):
    """Return a site only when it exists and belongs to the user's tenant."""
    site = model.query.filter_by(id=site_id).first()
    if site is None or not user_can_access_site(user, site):
        return None
    return site


def user_can_write_site(user: Any, site: Any) -> bool:
    if user is None or site is None:
        return False
    if getattr(site, "user_id", None) == getattr(user, "id", None):
        return True
    org_id = getattr(site, "organization_id", None)
    if not org_id:
        return False
    member = membership_for(user.id, org_id)
    return bool(member and member.role in WRITE_ROLES)


def sites_query_for_user(model: Any, user: Any):
    """Tenant-scoped site query: owned sites + org-shared sites."""
    from sqlalchemy import or_

    org_ids = user_org_ids(user.id)
    if not org_ids:
        return model.query.filter_by(user_id=user.id)
    return model.query.filter(
        or_(
            model.user_id == user.id,
            model.organization_id.in_(org_ids),
        )
    )


def latest_site_for_user(
    model: Any,
    user: Any,
    *,
    prefer_site_id: int | None = None,
):
    """Most recently *analyzed* site (updated_at), not first-seen (created_at).

    Re-scans bump ``updated_at`` while keeping the original ``created_at``. Ordering
    by created_at alone makes a newer preview/site (e.g. google.it claim) stick as
    dashboard ``latest`` forever, even after re-analyzing an older domain.
    """
    if prefer_site_id is not None:
        try:
            preferred = get_accessible_site(model, user, int(prefer_site_id))
        except (TypeError, ValueError):
            preferred = None
        if preferred is not None:
            return preferred
    return (
        sites_query_for_user(model, user)
        .order_by(
            model.updated_at.desc(),
            model.created_at.desc(),
            model.id.desc(),
        )
        .first()
    )
