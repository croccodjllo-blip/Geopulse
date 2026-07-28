"""Central plan entitlements for Centropic (Free vs Plus).

Single source of truth for feature gates and soft limits so routes,
templates and workers do not drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


CAPABILITIES = (
    "multi_site",
    "full_crawl",
    "competitors",
    "measured_sov",
    "prompt_bank",
    "scheduled_rescan",
    "api_access",
    "agency_whitelabel",
    "full_edge_signals",
    "extended_history",
    "pack_email",
)


@dataclass(frozen=True)
class PlanEntitlements:
    plan: str
    label: str
    is_pro: bool
    max_sites: int
    analysis_limit: int
    analysis_limit_lifetime: bool
    crawl_pages: int
    crawl_unlimited: bool
    history_limit: int
    capabilities: frozenset[str]

    def can(self, capability: str) -> bool:
        return capability in self.capabilities

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan,
            "label": self.label,
            "is_pro": self.is_pro,
            "max_sites": self.max_sites,
            "analysis_limit": self.analysis_limit,
            "analysis_limit_lifetime": self.analysis_limit_lifetime,
            "crawl_pages": self.crawl_pages,
            "crawl_unlimited": self.crawl_unlimited,
            "history_limit": self.history_limit,
            "capabilities": sorted(self.capabilities),
        }


def _plan_key(user: Any | None) -> str:
    if user is None:
        return "anonymous"
    if getattr(user, "is_admin", False) or (getattr(user, "plan", "") or "").lower() == "admin":
        return "admin"
    if getattr(user, "is_pro", False) or (getattr(user, "plan", "") or "").lower() in {
        "plus",
        "pro",
    }:
        return "plus"
    return "free"


def entitlements_for(
    user: Any | None,
    *,
    max_sites_free: int,
    max_sites_pro: int,
    free_total_analyses: int,
    pro_daily_analyses: int,
    free_crawl_pages: int,
    pro_crawl_pages: int,
    pro_crawl_unlimited: bool,
    free_history_limit: int,
    pro_history_limit: int,
) -> PlanEntitlements:
    key = _plan_key(user)
    if key in {"plus", "admin"}:
        caps = frozenset(CAPABILITIES)
        return PlanEntitlements(
            plan=key,
            label="Admin" if key == "admin" else "Plus",
            is_pro=True,
            max_sites=max_sites_pro,
            analysis_limit=pro_daily_analyses,
            analysis_limit_lifetime=False,
            crawl_pages=pro_crawl_pages,
            crawl_unlimited=bool(pro_crawl_unlimited),
            history_limit=pro_history_limit,
            capabilities=caps,
        )
    return PlanEntitlements(
        plan="free" if key == "free" else "anonymous",
        label="Free",
        is_pro=False,
        max_sites=max_sites_free,
        analysis_limit=free_total_analyses,
        analysis_limit_lifetime=True,
        crawl_pages=free_crawl_pages,
        crawl_unlimited=False,
        history_limit=free_history_limit,
        capabilities=frozenset({"pack_email"}),
    )


def require_capability(ents: PlanEntitlements, capability: str) -> str | None:
    """Return a user-facing block message, or None if allowed."""
    if ents.can(capability):
        return None
    labels = {
        "multi_site": "più siti",
        "full_crawl": "crawl intero sito",
        "competitors": "snapshot competitor",
        "measured_sov": "SoV measured / citation monitor",
        "prompt_bank": "prompt bank personalizzato",
        "scheduled_rescan": "re-scan schedulato",
        "api_access": "API key pubblica",
        "agency_whitelabel": "white-label agenzia",
        "full_edge_signals": "Edge Signals completo",
        "extended_history": "storico esteso",
    }
    feature = labels.get(capability, capability)
    return (
        f"{feature.capitalize()} è riservato al piano Plus. "
        "Sul Free restano score, findings e pack sullo stesso dominio."
    )


def missing_capabilities(
    ents: PlanEntitlements, needed: Iterable[str]
) -> list[str]:
    return [c for c in needed if not ents.can(c)]
