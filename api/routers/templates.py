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

@router.get("/api/templates")
def get_templates(conn=Depends(get_db)):
    return db.get_templates(conn)

@router.post("/api/templates")
def create_template(req: TemplateCreate, conn=Depends(get_db)):
    db.create_template(conn, req.title, req.subject, req.body)
    return {"status": "success"}

@router.delete("/api/templates/{template_id}")
def delete_template(template_id: int, conn=Depends(get_db)):
    db.delete_template(conn, template_id)
    return {"status": "success"}


# ----------------------------------------------------
# 4. Recipients Endpoints
# ----------------------------------------------------

