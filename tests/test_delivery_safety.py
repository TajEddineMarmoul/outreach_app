from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.delivery_safety import require_delivery_enabled
from src.platform.delivery_safety import delivery_enabled


def test_delivery_is_allowed_when_safe_mode_is_unset(monkeypatch):
    monkeypatch.delenv("OUTREACH_SAFE_LOCAL_MODE", raising=False)
    monkeypatch.delenv("OUTREACH_ALLOW_DELIVERY", raising=False)

    assert delivery_enabled()


def test_delivery_is_locked_in_safe_local_mode(monkeypatch):
    monkeypatch.setenv("OUTREACH_SAFE_LOCAL_MODE", "true")
    monkeypatch.delenv("OUTREACH_ALLOW_DELIVERY", raising=False)

    assert not delivery_enabled()
    with pytest.raises(HTTPException) as exc_info:
        require_delivery_enabled()

    assert exc_info.value.status_code == 403
    assert "Delivery is locked" in str(exc_info.value.detail)


def test_delivery_requires_explicit_opt_in_to_bypass_safe_mode(monkeypatch):
    monkeypatch.setenv("OUTREACH_SAFE_LOCAL_MODE", "true")
    monkeypatch.setenv("OUTREACH_ALLOW_DELIVERY", "true")

    assert delivery_enabled()
    require_delivery_enabled()
