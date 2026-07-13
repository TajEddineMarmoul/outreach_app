from __future__ import annotations

import json
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_current_user_id
from api.schemas import SettingsUpdate
from src.gmail_sender import credentials_file_path
from src.platform.db import get_session
from src.platform.models import UserSettings
from src.platform.services import ensure_user


router = APIRouter()
DEFAULT_SETTINGS = {
    "max_daily_cap": 50,
    "bounce_rate_pause_threshold": 5.0,
    "max_consecutive_errors": 3,
}


class CredentialsContent(BaseModel):
    content: str


@router.get("/api/settings")
def get_settings(
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    ensure_user(session, user_id)
    settings = session.get(UserSettings, user_id)
    defaults = {**DEFAULT_SETTINGS, **(settings.defaults or {})}
    session.commit()
    return {
        "timezone": settings.timezone,
        "max_daily_cap": defaults["max_daily_cap"],
        "bounce_rate_pause_threshold": defaults["bounce_rate_pause_threshold"],
        "max_consecutive_errors": defaults["max_consecutive_errors"],
    }


@router.patch("/api/settings")
def patch_settings(
    req: SettingsUpdate,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    try:
        ZoneInfo(req.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=422, detail="Unknown IANA timezone")

    ensure_user(session, user_id)
    settings = session.get(UserSettings, user_id)
    settings.timezone = req.timezone
    settings.defaults = {
        **(settings.defaults or {}),
        "max_daily_cap": req.max_daily_cap,
        "bounce_rate_pause_threshold": req.bounce_rate_pause_threshold,
        "max_consecutive_errors": req.max_consecutive_errors,
    }
    session.commit()
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
