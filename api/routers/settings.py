from __future__ import annotations

import json
import os

os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import config_path, db, get_current_user_id, get_db
from api.schemas import SettingsUpdate
from src.gmail_sender import credentials_file_path
from src.models import load_config


router = APIRouter()


class CredentialsContent(BaseModel):
    content: str


@router.get("/api/settings")
def get_settings(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    config = load_config(config_path())
    return {
        "timezone": db.get_setting(conn, "timezone", config.timezone, user_id),
        "max_daily_cap": db.get_setting(
            conn,
            "max_daily_cap",
            config.sending.max_daily_cap_allowed_without_manual_override,
            user_id,
        ),
        "bounce_rate_pause_threshold": db.get_setting(
            conn,
            "bounce_rate_pause_threshold",
            config.sending.bounce_rate_pause_threshold,
            user_id,
        ),
        "max_consecutive_errors": db.get_setting(
            conn,
            "max_consecutive_errors",
            config.sending.max_consecutive_errors,
            user_id,
        ),
        "config_path": str(config_path()),
    }


@router.patch("/api/settings")
def patch_settings(
    req: SettingsUpdate,
    conn=Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    db.set_setting(conn, "timezone", req.timezone, user_id)
    db.set_setting(conn, "max_daily_cap", req.max_daily_cap, user_id)
    db.set_setting(conn, "bounce_rate_pause_threshold", req.bounce_rate_pause_threshold, user_id)
    db.set_setting(conn, "max_consecutive_errors", req.max_consecutive_errors, user_id)
    return {"status": "success"}


@router.get("/api/oauth/status")
def get_oauth_status(_user_id: str = Depends(get_current_user_id)):
    return {"credentials_json_present": credentials_file_path().exists()}


@router.post("/api/oauth/save-credentials-json")
def save_credentials(
    req: CredentialsContent,
    _user_id: str = Depends(get_current_user_id),
):
    try:
        data = json.loads(req.content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")

    client_section = data.get("web") or data.get("installed")
    if not client_section:
        raise HTTPException(status_code=400, detail="OAuth JSON must contain a 'web' or 'installed' key")

    client_id = (client_section.get("client_id") or "").strip()
    client_secret = (client_section.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Missing client_id or client_secret")

    path = credentials_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"status": "success", "client_type": "web" if "web" in data else "installed"}
