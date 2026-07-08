from __future__ import annotations

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from fastapi import APIRouter

from api.deps import get_db_path, config_path
from api.schemas import SettingsUpdate
from src.models import load_config, save_config

router = APIRouter()

@router.get("/api/settings")
def get_settings():
    config = load_config(config_path())
    return {
        "timezone": config.timezone,
        "max_daily_cap": config.sending.max_daily_cap_allowed_without_manual_override,
        "bounce_rate_pause_threshold": config.sending.bounce_rate_pause_threshold,
        "max_consecutive_errors": config.sending.max_consecutive_errors,
        "database_path": str(get_db_path()),
        "config_path": str(config_path()),
    }

@router.patch("/api/settings")
def patch_settings(req: SettingsUpdate):
    config = load_config(config_path())
    config.timezone = req.timezone
    config.sending.max_daily_cap_allowed_without_manual_override = req.max_daily_cap
    config.sending.bounce_rate_pause_threshold = req.bounce_rate_pause_threshold
    config.sending.max_consecutive_errors = req.max_consecutive_errors
    save_config(config, config_path())
    return {"status": "success"}

