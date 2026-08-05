"""Internal/demo users skip site and analysis soft quotas."""

from __future__ import annotations

from types import SimpleNamespace

from services.usage_billing import is_unlimited_user


def test_is_unlimited_user_for_internal_role():
    free_internal = SimpleNamespace(is_admin=False, plan="free", role="internal")
    plus_internal = SimpleNamespace(is_admin=False, plan="plus", role="internal")
    biz_internal = SimpleNamespace(is_admin=False, plan="business", role="internal")
    normal_free = SimpleNamespace(is_admin=False, plan="free", role=None)

    assert is_unlimited_user(free_internal) is True
    assert is_unlimited_user(plus_internal) is True
    assert is_unlimited_user(biz_internal) is True
    assert is_unlimited_user(normal_free) is False


def test_enforce_analyze_limits_skips_unlimited():
    from app import enforce_analyze_limits

    user = SimpleNamespace(is_admin=False, plan="free", role="internal")
    assert enforce_analyze_limits(user, url="https://example.com", existing=None) is None
