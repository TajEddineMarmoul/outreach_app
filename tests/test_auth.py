from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api import auth


def credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_private_access_token_maps_to_configured_user(monkeypatch):
    monkeypatch.setattr(auth, "APP_ACCESS_TOKEN", "private-token")
    monkeypatch.setattr(auth, "APP_USER_ID", "production-user")
    monkeypatch.setattr(auth, "IS_PRODUCTION", True)

    assert auth.get_current_user_id(credentials("private-token")) == "production-user"


def test_private_access_token_rejects_every_other_token(monkeypatch):
    monkeypatch.setattr(auth, "APP_ACCESS_TOKEN", "private-token")
    monkeypatch.setattr(auth, "APP_USER_ID", "production-user")
    monkeypatch.setattr(auth, "IS_PRODUCTION", True)

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user_id(credentials("some-other-token"))

    assert exc_info.value.status_code == 401


def test_private_access_token_requires_user_mapping(monkeypatch):
    monkeypatch.setattr(auth, "APP_ACCESS_TOKEN", "private-token")
    monkeypatch.setattr(auth, "APP_USER_ID", "")
    monkeypatch.setattr(auth, "IS_PRODUCTION", True)

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user_id(credentials("private-token"))

    assert exc_info.value.status_code == 503


def test_mock_tokens_remain_available_only_outside_production(monkeypatch):
    monkeypatch.setattr(auth, "APP_ACCESS_TOKEN", "")
    monkeypatch.setattr(auth, "APP_USER_ID", "")
    monkeypatch.setattr(auth, "IS_PRODUCTION", False)
    assert auth.get_current_user_id(credentials("mock_test_user")) == "mock_test_user"

    monkeypatch.setattr(auth, "IS_PRODUCTION", True)
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user_id(credentials("mock_test_user"))

    assert exc_info.value.status_code == 401


def test_local_development_identity_maps_to_configured_user(monkeypatch):
    monkeypatch.setattr(auth, "APP_ACCESS_TOKEN", "")
    monkeypatch.setattr(auth, "APP_USER_ID", "")
    monkeypatch.setattr(auth, "LOCAL_DEV_USER_ID", "production-user")
    monkeypatch.setattr(auth, "IS_PRODUCTION", False)

    assert auth.get_current_user_id(credentials("local_dev_production-user")) == "production-user"


def test_local_development_identity_is_rejected_in_production(monkeypatch):
    monkeypatch.setattr(auth, "APP_ACCESS_TOKEN", "")
    monkeypatch.setattr(auth, "APP_USER_ID", "")
    monkeypatch.setattr(auth, "LOCAL_DEV_USER_ID", "production-user")
    monkeypatch.setattr(auth, "IS_PRODUCTION", True)

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user_id(credentials("local_dev_production-user"))

    assert exc_info.value.status_code == 401
