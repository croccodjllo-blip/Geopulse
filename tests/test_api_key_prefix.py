"""Centropic API keys use ct_ while legacy gp_ keys remain valid."""

from __future__ import annotations

from types import SimpleNamespace

from services.api_auth import find_user_by_api_key, generate_api_key, hash_api_key


class _Query:
    def __init__(self, users):
        self.users = users

    def filter_by(self, **filters):
        match = next(
            (
                user
                for user in self.users
                if all(getattr(user, key, None) == value for key, value in filters.items())
            ),
            None,
        )
        return SimpleNamespace(first=lambda: match)


def test_generate_api_key_uses_centropic_prefix():
    raw, prefix, digest = generate_api_key()

    assert raw.startswith("ct_")
    assert prefix == raw[:10]
    assert digest == hash_api_key(raw)


def test_find_user_accepts_centropic_and_legacy_prefixes():
    centropic_raw = "ct_current-example-key"
    legacy_raw = "gp_legacy-example-key"
    centropic_user = SimpleNamespace(api_key_hash=hash_api_key(centropic_raw))
    legacy_user = SimpleNamespace(api_key_hash=hash_api_key(legacy_raw))
    User = SimpleNamespace(query=_Query([centropic_user, legacy_user]))

    assert find_user_by_api_key(User, centropic_raw) is centropic_user
    assert find_user_by_api_key(User, legacy_raw) is legacy_user
    assert find_user_by_api_key(User, "xx_unknown") is None
