from __future__ import annotations

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

import sys
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional, List, Dict
import pandas as pd
from io import StringIO

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# Ensure root project dir is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import db
from src.models import (
    AppConfig,
    load_config,
    save_config,
    ContactStatus,
    DEFAULT_BODY_TEMPLATE,
    DEFAULT_FALLBACK_BODY_TEMPLATE,
    DEFAULT_SUBJECT_TEMPLATE,
)
from src.gmail_sender import (
    connect_and_get_profile,
    connect_sender_account,
    credentials_file_path,
    default_token_path,
    gmail_connection_status,
)
from src.google_sheets import (
    get_public_sheet_csv,
    get_published_csv,
    list_public_sheet_tabs,
    parse_google_sheet_url_details,
)
from src.importer import (
    import_dataframe,
    normalize_email,
    detect_columns,
)
from src.safety import (
    campaign_checklist,
    pre_send_checks,
)
from src.scheduler import (
    start_background_autopilot,
    stop_autopilot,
    send_test_email,
)
from src.analytics import send_log_dataframe
from src.dnc import add_email as dnc_add_email, rows as dnc_rows

from fastapi import APIRouter

router = APIRouter()



# Startup Context Settings
def get_db_path() -> Path:
    return db.get_db_path(os.getenv("OUTREACH_DB_PATH", "data/outreach.db"))

def config_path() -> Path:
    return db.resolve_project_path(os.getenv("OUTREACH_CONFIG_PATH", "config.yaml"), PROJECT_ROOT)

def get_db():
    conn = db.init_db(get_db_path())
    try:
        yield conn
    finally:
        conn.close()



# Pydantic schemas
class CampaignCreate(BaseModel):
    name: str

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    fallback_body_template: Optional[str] = None
    attachment_path: Optional[str] = None
    require_attachment: Optional[bool] = None
    tracking_enabled: Optional[bool] = None
    unsubscribe_link: Optional[bool] = None

class ComposerUpdate(BaseModel):
    subject_template: str
    body_template: str
    fallback_body_template: str
    attachment_path: str
    require_attachment: Optional[bool] = False

class SendSettingsUpdate(BaseModel):
    days: List[str]
    start_time: str
    end_time: str
    daily_cap: int
    delay_minutes: int
    sender_daily_cap: Optional[int] = None

class SenderSelect(BaseModel):
    sender_id: int

class RecipientsPaste(BaseModel):
    raw: str

class RecipientsGoogleSheet(BaseModel):
    url: str
    tab_name: str
    header_row: int
    use_private: Optional[bool] = False
    mapping: Dict[str, str]

class RecipientsSelectExisting(BaseModel):
    contact_ids: List[int]

class TestSendRequest(BaseModel):
    recipient_email: str
    preview_contact_id: Optional[int] = None

class SettingsUpdate(BaseModel):
    timezone: str
    max_daily_cap: int
    bounce_rate_pause_threshold: float
    max_consecutive_errors: int

class SaveCredentialsRequest(BaseModel):
    content: str


# ----------------------------------------------------
# 1. Campaigns Endpoints
# ----------------------------------------------------

@router.get("/api/senders")
def list_senders(conn=Depends(get_db)):
    senders = db.list_senders(conn)
    return [dict(sender) for sender in senders]

@router.post("/api/senders/connect")
def connect_sender(conn=Depends(get_db)):
    if not credentials_file_path().exists():
        raise HTTPException(status_code=400, detail="Gmail client credentials.json missing")
    try:
        connected = connect_sender_account(force_reauth=True)
        sender_id = db.upsert_sender(
            conn,
            email=connected.email,
            display_name="Default sender",
            token_path=connected.token_path,
            daily_cap=10,
            status="connected",
        )
        db.set_setting(conn, "sender_email", connected.email)
        return {"id": sender_id, "email": connected.email}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/api/senders/{sender_id}/reconnect")
def reconnect_sender(sender_id: int, conn=Depends(get_db)):
    sender = conn.execute("SELECT * FROM senders WHERE id = ?", (sender_id,)).fetchone()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    try:
        connected = connect_and_get_profile(
            force_reauth=True,
            token_path=Path(sender["token_path"]),
            prompt="select_account consent",
        )
        return {"status": "success", "email": connected.email}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.patch("/api/senders/{sender_id}")
def update_sender(sender_id: int, req: SenderUpdate, conn=Depends(get_db)):
    sender = db.get_sender(conn, sender_id)
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    db.update_sender(conn, sender_id, req.display_name, req.daily_cap, req.group_name)
    return {"status": "success"}


@router.delete("/api/senders/{sender_id}")
def delete_sender(sender_id: int, conn=Depends(get_db)):
    sender = db.get_sender(conn, sender_id)
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    db.remove_sender(conn, sender_id)
    return {"status": "success"}


@router.post("/api/senders/{sender_id}/set-default")
def set_default_sender(sender_id: int, conn=Depends(get_db)):
    sender = db.get_sender(conn, sender_id)
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    db.set_default_sender(conn, sender_id)
    return {"status": "success"}


# ----------------------------------------------------
# 3b. Group Endpoints
# ----------------------------------------------------

class GroupCreate(BaseModel):
    name: str

@router.get("/api/groups")
def get_groups(conn=Depends(get_db)):
    saved = db.get_setting(conn, "sender_groups", [])
    db_groups = [
        row["group_name"]
        for row in conn.execute("SELECT DISTINCT group_name FROM senders WHERE group_name != ''").fetchall()
    ]
    all_groups = sorted(set(saved + db_groups))
    return all_groups

@router.post("/api/groups")
def create_group(req: GroupCreate, conn=Depends(get_db)):
    groups = db.get_setting(conn, "sender_groups", [])
    if req.name in groups:
        raise HTTPException(status_code=400, detail="Group already exists")
    groups.append(req.name)
    db.set_setting(conn, "sender_groups", sorted(groups))
    return {"status": "success"}

@router.delete("/api/groups/{group_name}")
def delete_group(group_name: str, conn=Depends(get_db)):
    groups = db.get_setting(conn, "sender_groups", [])
    if group_name not in groups:
        raise HTTPException(status_code=404, detail="Group not found")
    groups.remove(group_name)
    db.set_setting(conn, "sender_groups", groups)
    return {"status": "success"}


# ----------------------------------------------------
# 3c. Template Endpoints
# ----------------------------------------------------

class TemplateCreate(BaseModel):
    title: str
    subject: str
    body: str

