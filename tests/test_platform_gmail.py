from __future__ import annotations

import json
from types import SimpleNamespace

from src.platform import gmail as platform_gmail


def test_legacy_sender_refresh_keeps_its_original_granted_scopes(monkeypatch):
    """A tracking permission added later must not break an existing sender."""

    legacy_scopes = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/userinfo.email",
    ]
    captured: dict[str, object] = {}

    class FakeCredentials:
        expired = False
        refresh_token = None
        valid = True

    def from_authorized_user_info(payload, scopes=None):
        captured["payload"] = payload
        captured["scopes"] = scopes
        return FakeCredentials()

    monkeypatch.setattr(
        platform_gmail,
        "decrypt_text",
        lambda _value: json.dumps({"client_id": "client", "refresh_token": "refresh", "client_secret": "secret"}),
    )
    monkeypatch.setattr(
        platform_gmail.Credentials,
        "from_authorized_user_info",
        from_authorized_user_info,
    )
    sender = SimpleNamespace(
        encrypted_oauth_credentials="encrypted",
        scopes=legacy_scopes,
    )

    credentials = platform_gmail.credentials_from_sender(SimpleNamespace(), sender)

    assert isinstance(credentials, FakeCredentials)
    assert captured["scopes"] == legacy_scopes
    assert "https://www.googleapis.com/auth/gmail.readonly" not in captured["scopes"]


def test_sender_without_saved_scope_metadata_uses_the_token_scope_metadata(monkeypatch):
    """Older imported records can rely on the scopes embedded in their token."""

    captured: dict[str, object] = {}

    class FakeCredentials:
        expired = False
        refresh_token = None
        valid = True

    def from_authorized_user_info(_payload, scopes=None):
        captured["scopes"] = scopes
        return FakeCredentials()

    monkeypatch.setattr(
        platform_gmail,
        "decrypt_text",
        lambda _value: json.dumps({"client_id": "client", "refresh_token": "refresh", "client_secret": "secret"}),
    )
    monkeypatch.setattr(
        platform_gmail.Credentials,
        "from_authorized_user_info",
        from_authorized_user_info,
    )
    sender = SimpleNamespace(encrypted_oauth_credentials="encrypted", scopes=[])

    platform_gmail.credentials_from_sender(SimpleNamespace(), sender)

    assert captured["scopes"] is None
