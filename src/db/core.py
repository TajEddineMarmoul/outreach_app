from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.db.connection import PGConnection, get_connection as _get_conn
from src.models import STATUS_VALUES

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolve_project_path(path: str | Path, root: Path = PROJECT_ROOT) -> Path:
    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return root / path_obj


def connect() -> PGConnection:
    return _get_conn()


def init_db() -> PGConnection:
    conn = connect()
    create_tables(conn)
    return conn


def create_tables(conn: PGConnection) -> None:
    _create_pg_tables(conn)
    conn.commit()


def _create_pg_tables(conn: PGConnection) -> None:
    status_sql = "', '".join(STATUS_VALUES)
    conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS contacts (
            id SERIAL PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT DEFAULT '',
            full_name TEXT DEFAULT '',
            email TEXT NOT NULL,
            company_name TEXT NOT NULL,
            company_website TEXT DEFAULT '',
            linkedin TEXT DEFAULT '',
            title TEXT DEFAULT '',
            industry TEXT DEFAULT '',
            keywords TEXT DEFAULT '',
            keyword_1 TEXT DEFAULT '',
            keyword_2 TEXT DEFAULT '',
            keyword_3 TEXT DEFAULT '',
            country TEXT DEFAULT '',
            source_type TEXT DEFAULT 'csv',
            source_url TEXT DEFAULT '',
            sheet_id TEXT DEFAULT '',
            sheet_name TEXT DEFAULT '',
            last_synced_at TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            preview_generated_at TEXT,
            last_preview_subject TEXT,
            last_preview_body TEXT,
            custom_fields TEXT DEFAULT '{{}}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            user_id TEXT,
            UNIQUE(email, user_id)
        );
        CREATE TABLE IF NOT EXISTS campaigns (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            subject_template TEXT NOT NULL,
            body_template TEXT NOT NULL,
            fallback_body_template TEXT NOT NULL,
            attachment_path TEXT DEFAULT '',
            selected_sender_id INTEGER,
            status TEXT NOT NULL DEFAULT 'stopped',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            user_id TEXT
        );
        CREATE TABLE IF NOT EXISTS senders (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            token_path TEXT NOT NULL,
            connected_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'connected',
            daily_cap INTEGER NOT NULL DEFAULT 10,
            is_default INTEGER NOT NULL DEFAULT 0,
            user_id TEXT,
            UNIQUE(email, user_id)
        );
        CREATE TABLE IF NOT EXISTS templates (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            user_id TEXT
        );
        CREATE TABLE IF NOT EXISTS campaign_recipients (
            campaign_id INTEGER NOT NULL,
            contact_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(campaign_id, contact_id)
        );
        CREATE TABLE IF NOT EXISTS send_log (
            id SERIAL PRIMARY KEY,
            contact_id INTEGER,
            campaign_id INTEGER,
            recipient_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body_snapshot TEXT NOT NULL,
            sent_at TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            gmail_message_id TEXT,
            gmail_thread_id TEXT,
            sender_id INTEGER,
            sender_email TEXT,
            attachment_name TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            user_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_send_log_status_created ON send_log(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_send_log_contact_status ON send_log(contact_id, status);
        CREATE INDEX IF NOT EXISTS idx_campaign_recipients_contact ON campaign_recipients(contact_id);
        CREATE TABLE IF NOT EXISTS do_not_contact (
            email TEXT,
            user_id TEXT,
            reason TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            PRIMARY KEY (email, user_id)
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT,
            user_id TEXT,
            value TEXT NOT NULL,
            PRIMARY KEY (key, user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_senders_user ON senders(user_id);
        CREATE INDEX IF NOT EXISTS idx_templates_user ON templates(user_id);
        CREATE INDEX IF NOT EXISTS idx_settings_user ON settings(user_id);
    """)


def set_setting(conn, key: str, value: Any, user_id: str = "default_user") -> None:
    conn.execute(
        """
        INSERT INTO settings(key, user_id, value)
        VALUES(?, ?, ?)
        ON CONFLICT(key, user_id) DO UPDATE SET value = excluded.value
        """,
        (key, user_id, json.dumps(value)),
    )
    conn.commit()


def get_setting(conn, key: str, default: Any = None, user_id: str = "default_user") -> Any:
    row = conn.execute("SELECT value FROM settings WHERE key = ? AND user_id = ?", (key, user_id)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(str(row["value"]))
    except json.JSONDecodeError:
        return row["value"]



