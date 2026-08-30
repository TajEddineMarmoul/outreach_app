"""Explicit local-delivery safety controls.

Reading a shared production database locally is useful, but delivery must be
an intentional opt-in.  These flags are evaluated at call time so a restarted
local service immediately picks up an environment change.
"""

from __future__ import annotations

import os


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def delivery_enabled() -> bool:
    """Whether this process may create or process real delivery work."""
    return not _env_flag("OUTREACH_SAFE_LOCAL_MODE") or _env_flag("OUTREACH_ALLOW_DELIVERY")


def delivery_block_reason() -> str:
    return (
        "Delivery is locked in safe local mode. Set OUTREACH_ALLOW_DELIVERY=true "
        "and restart the services only when you intentionally want to send live email."
    )
