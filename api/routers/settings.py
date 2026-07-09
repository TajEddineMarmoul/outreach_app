from __future__ import annotations

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from fastapi import APIRouter, Depends

from api.deps import db, get_db, get_current_user_id, get_db_path, config_path
from api.schemas import SettingsUpdate
from src.models import load_config

router = APIRouter()

@router.get("/api/settings")
def get_settings(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    config = load_config(config_path())
    
    timezone = db.get_setting(conn, "timezone", config.timezone, user_id)
    max_daily_cap = db.get_setting(conn, "max_daily_cap", config.sending.max_daily_cap_allowed_without_manual_override, user_id)
    bounce_rate_pause_threshold = db.get_setting(conn, "bounce_rate_pause_threshold", config.sending.bounce_rate_pause_threshold, user_id)
    max_consecutive_errors = db.get_setting(conn, "max_consecutive_errors", config.sending.max_consecutive_errors, user_id)
    
    return {
        "timezone": timezone,
        "max_daily_cap": max_daily_cap,
        "bounce_rate_pause_threshold": bounce_rate_pause_threshold,
        "max_consecutive_errors": max_consecutive_errors,
        "database_path": str(get_db_path()),
        "config_path": str(config_path()),
    }

@router.patch("/api/settings")
def patch_settings(req: SettingsUpdate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    db.set_setting(conn, "timezone", req.timezone, user_id)
    db.set_setting(conn, "max_daily_cap", req.max_daily_cap, user_id)
    db.set_setting(conn, "bounce_rate_pause_threshold", req.bounce_rate_pause_threshold, user_id)
    db.set_setting(conn, "max_consecutive_errors", req.max_consecutive_errors, user_id)
    return {"status": "success"}
