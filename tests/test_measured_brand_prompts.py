"""Measured brand/prompts must follow the analyzed site, not account company."""

from __future__ import annotations

from types import SimpleNamespace

from services.prompt_bank import resolve_prompts, site_prompts
from services.sov_measured import (
    brand_from_domain,
    is_user_owned_domain,
    resolve_measured_brand,
)


def test_brand_from_domain():
    assert brand_from_domain("www.nike.com") == "Nike"
    assert brand_from_domain("https://adidas.com/") == "Adidas"


def test_is_user_owned_domain():
    user = SimpleNamespace(
        website_url="https://centropic.ai/",
        company="centropic.ai",
    )
    assert is_user_owned_domain(user, "centropic.ai") is True
    assert is_user_owned_domain(user, "www.centropic.ai") is True
    assert is_user_owned_domain(user, "nike.com") is False


def test_resolve_measured_brand_ignores_host_title():
    user = SimpleNamespace(website_url="https://centropic.ai/", company="centropic.ai")
    brand = resolve_measured_brand(
        user=user,
        domain="www.nike.com",
        scraped={"title": "www.nike.com", "entity": {"brand_name": ""}},
    )
    assert brand == "Nike"


def test_resolve_measured_brand_own_site_uses_company_name():
    user = SimpleNamespace(
        website_url="https://centropic.ai/",
        company="Centropic",
    )
    brand = resolve_measured_brand(
        user=user,
        domain="centropic.ai",
        scraped={"entity": {"brand_name": ""}},
    )
    assert brand == "Centropic"


def test_site_prompts_mention_brand():
    prompts = site_prompts(brand="Nike", domain="nike.com", locale="it")
    assert any("Nike" in p for p in prompts)
    assert not any("Centropic" in p for p in prompts)


def test_resolve_prompts_third_party_not_centropic_defaults():
    user = SimpleNamespace(
        website_url="https://centropic.ai/",
        company="centropic.ai",
        prompt_bank_json=None,
    )
    prompts = resolve_prompts(
        user=user,
        locale="it",
        domain="nike.com",
        brand="Nike",
        own_site=False,
        max_prompts=6,
    )
    joined = " ".join(prompts)
    assert "Nike" in joined
    assert "Centropic" not in joined
    assert "llms.txt" not in joined
