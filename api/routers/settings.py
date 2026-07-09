from __future__ import annotations

import json
import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import db, get_db, get_current_user_id, get_db_path, config_path
from api.schemas import SettingsUpdate
from src.models import load_config
from src.gmail_sender import credentials_file_path, save_credentials_json

router = APIRouter()


class CredentialsContent(BaseModel):
    content: str

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

@router.get("/api/oauth/status")
def get_oauth_status(user_id: str = Depends(get_current_user_id)):
    path = credentials_file_path()
    return {"credentials_json_present": path.exists()}

@router.post("/api/oauth/save-credentials-json")
def save_credentials(req: CredentialsContent, user_id: str = Depends(get_current_user_id)):
    try:
        data = json.loads(req.content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")

    client_section = data.get("web")
    if not client_section:
        raise HTTPException(status_code=400, detail="Only Web application OAuth client JSON is supported. Create a 'Web application' client in Google Cloud Console.")

    client_id = (client_section.get("client_id") or "").strip()
    client_secret = (client_section.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Missing client_id or client_secret")

    path = credentials_file_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"status": "success", "client_type": "web"}
