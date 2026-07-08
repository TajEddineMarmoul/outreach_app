from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.models import (
    DEFAULT_BODY_TEMPLATE,
    DEFAULT_FALLBACK_BODY_TEMPLATE,
    DEFAULT_SUBJECT_TEMPLATE,
    STATUS_VALUES,
    ContactStatus,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "outreach.db"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolve_project_path(path: str | Path, root: Path = PROJECT_ROOT) -> Path:
    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return root / path_obj


def get_db_path(path: str | Path | None = None) -> Path:
    raw = path or os.getenv("OUTREACH_DB_PATH") or DEFAULT_DB_PATH
    return resolve_project_path(raw)


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    final_path = get_db_path(db_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(final_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    conn = connect(db_path)
    create_tables(conn)
        
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    status_sql = "', '".join(STATUS_VALUES)
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT DEFAULT '',
            full_name TEXT DEFAULT '',
            email TEXT NOT NULL UNIQUE,
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
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('{status_sql}')),
            preview_generated_at TEXT,
            last_preview_subject TEXT,
            last_preview_body TEXT,
            custom_fields TEXT DEFAULT '{{}}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject_template TEXT NOT NULL,
            body_template TEXT NOT NULL,
            fallback_body_template TEXT NOT NULL,
            attachment_path TEXT DEFAULT '',
            selected_sender_id INTEGER,
            status TEXT NOT NULL DEFAULT 'stopped',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(selected_sender_id) REFERENCES senders(id)
        );

        CREATE TABLE IF NOT EXISTS senders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            display_name TEXT DEFAULT '',
            token_path TEXT NOT NULL,
            connected_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'connected',
            daily_cap INTEGER NOT NULL DEFAULT 10,
            is_default INTEGER NOT NULL DEFAULT 0,
            group_name TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS campaign_recipients (
            campaign_id INTEGER NOT NULL,
            contact_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(campaign_id, contact_id),
            FOREIGN KEY(campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
            FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS send_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            FOREIGN KEY(contact_id) REFERENCES contacts(id),
            FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
            FOREIGN KEY(sender_id) REFERENCES senders(id)
        );

        CREATE INDEX IF NOT EXISTS idx_send_log_status_created
            ON send_log(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_send_log_contact_status
            ON send_log(contact_id, status);
        CREATE INDEX IF NOT EXISTS idx_campaign_recipients_contact
            ON campaign_recipients(contact_id);

        CREATE TABLE IF NOT EXISTS do_not_contact (
            email TEXT PRIMARY KEY,
            reason TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    migrate_schema(conn)
    conn.commit()


def migrate_schema(conn: sqlite3.Connection) -> None:
    contact_columns = {row["name"] for row in conn.execute("PRAGMA table_info(contacts)").fetchall()}
    additions = {
        "source_type": "TEXT DEFAULT 'csv'",
        "source_url": "TEXT DEFAULT ''",
        "sheet_id": "TEXT DEFAULT ''",
        "sheet_name": "TEXT DEFAULT ''",
        "last_synced_at": "TEXT",
        "custom_fields": "TEXT DEFAULT '{}'",
    }
    for column, definition in additions.items():
        if column not in contact_columns:
            conn.execute(f"ALTER TABLE contacts ADD COLUMN {column} {definition}")

    campaign_columns = {row["name"] for row in conn.execute("PRAGMA table_info(campaigns)").fetchall()}
    if "selected_sender_id" not in campaign_columns:
        conn.execute("ALTER TABLE campaigns ADD COLUMN selected_sender_id INTEGER")

    send_log_columns = {row["name"] for row in conn.execute("PRAGMA table_info(send_log)").fetchall()}
    if "sender_id" not in send_log_columns:
        conn.execute("ALTER TABLE send_log ADD COLUMN sender_id INTEGER")
    if "sender_email" not in send_log_columns:
        conn.execute("ALTER TABLE send_log ADD COLUMN sender_email TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_send_log_sender_status ON send_log(sender_id, status)"
    )

    sender_columns = {row["name"] for row in conn.execute("PRAGMA table_info(senders)").fetchall()}
    if "group_name" not in sender_columns:
        conn.execute("ALTER TABLE senders ADD COLUMN group_name TEXT NOT NULL DEFAULT ''")


def set_setting(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        INSERT INTO settings(key, value)
        VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, json.dumps(value)),
    )
    conn.commit()


def get_setting(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(str(row["value"]))
    except json.JSONDecodeError:
        return row["value"]

