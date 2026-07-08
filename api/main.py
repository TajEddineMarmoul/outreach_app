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

app = FastAPI(title="Outreach App API", version="1.0.0")

# CORS middleware for Next.js frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.on_event("startup")
def on_startup():
    conn = db.init_db(get_db_path())
    conn.close()

# Pydantic schemas

from api.routers import campaigns, senders, contacts, templates, settings

app.include_router(campaigns.router)
app.include_router(senders.router)
app.include_router(contacts.router)
app.include_router(templates.router)
app.include_router(settings.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
