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
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('{status_sql}')),
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
            user_id TEXT,
            FOREIGN KEY(selected_sender_id) REFERENCES senders(id)
        );

        CREATE TABLE IF NOT EXISTS senders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            token_path TEXT NOT NULL,
            connected_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'connected',
            daily_cap INTEGER NOT NULL DEFAULT 10,
            is_default INTEGER NOT NULL DEFAULT 0,
            group_name TEXT NOT NULL DEFAULT '',
            user_id TEXT,
            UNIQUE(email, user_id)
        );

        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            user_id TEXT
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
            user_id TEXT,
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
        """
    )
    migrate_schema(conn)
    conn.commit()


def migrate_schema(conn: sqlite3.Connection) -> None:
    # 1. Migrate contacts (handle user_id and email uniqueness change if needed)
    contact_columns = {row["name"] for row in conn.execute("PRAGMA table_info(contacts)").fetchall()}
    additions = {
        "source_type": "TEXT DEFAULT 'csv'",
        "source_url": "TEXT DEFAULT ''",
        "sheet_id": "TEXT DEFAULT ''",
        "sheet_name": "TEXT DEFAULT ''",
        "last_synced_at": "TEXT",
        "custom_fields": "TEXT DEFAULT '{}'",
        "user_id": "TEXT",
    }
    
    # If the old database doesn't have user_id, it means we need to migrate the uniqueness constraint as well
    # Recreating the table is the cleanest way to do this in SQLite
    if "user_id" not in contact_columns:
        status_sql = "', '".join(STATUS_VALUES)
        conn.executescript(
            f"""
            ALTER TABLE contacts RENAME TO contacts_old;
            CREATE TABLE contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('{status_sql}')),
                preview_generated_at TEXT,
                last_preview_subject TEXT,
                last_preview_body TEXT,
                custom_fields TEXT DEFAULT '{{}}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                user_id TEXT,
                UNIQUE(email, user_id)
            );
            INSERT OR IGNORE INTO contacts (id, first_name, last_name, full_name, email, company_name, company_website, linkedin, title, industry, keywords, keyword_1, keyword_2, keyword_3, country, source_type, source_url, sheet_id, sheet_name, last_synced_at, status, preview_generated_at, last_preview_subject, last_preview_body, custom_fields, created_at, updated_at, user_id)
            SELECT id, first_name, last_name, full_name, email, company_name, company_website, linkedin, title, industry, keywords, keyword_1, keyword_2, keyword_3, country, source_type, source_url, sheet_id, sheet_name, last_synced_at, status, preview_generated_at, last_preview_subject, last_preview_body, custom_fields, created_at, updated_at, 'default_user' FROM contacts_old;
            DROP TABLE contacts_old;
            """
        )
    else:
        for column, definition in additions.items():
            if column not in contact_columns:
                conn.execute(f"ALTER TABLE contacts ADD COLUMN {column} {definition}")
                
    conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_user ON contacts(user_id);")

    # 2. Migrate campaigns
    campaign_columns = {row["name"] for row in conn.execute("PRAGMA table_info(campaigns)").fetchall()}
    if "selected_sender_id" not in campaign_columns:
        conn.execute("ALTER TABLE campaigns ADD COLUMN selected_sender_id INTEGER")
    if "user_id" not in campaign_columns:
        conn.execute("ALTER TABLE campaigns ADD COLUMN user_id TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_campaigns_user ON campaigns(user_id);")

    # 3. Migrate senders (handle user_id and email uniqueness change if needed)
    sender_columns = {row["name"] for row in conn.execute("PRAGMA table_info(senders)").fetchall()}
    if "user_id" not in sender_columns:
        conn.executescript(
            """
            ALTER TABLE senders RENAME TO senders_old;
            CREATE TABLE senders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                display_name TEXT DEFAULT '',
                token_path TEXT NOT NULL,
                connected_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'connected',
                daily_cap INTEGER NOT NULL DEFAULT 10,
                is_default INTEGER NOT NULL DEFAULT 0,
                group_name TEXT NOT NULL DEFAULT '',
                user_id TEXT,
                UNIQUE(email, user_id)
            );
            INSERT OR IGNORE INTO senders (id, email, display_name, token_path, connected_at, status, daily_cap, is_default, group_name, user_id)
            SELECT id, email, display_name, token_path, connected_at, status, daily_cap, is_default, group_name, 'default_user' FROM senders_old;
            DROP TABLE senders_old;
            """
        )
    else:
        if "group_name" not in sender_columns:
            conn.execute("ALTER TABLE senders ADD COLUMN group_name TEXT NOT NULL DEFAULT ''")
            
    conn.execute("CREATE INDEX IF NOT EXISTS idx_senders_user ON senders(user_id);")

    # 4. Migrate templates
    template_columns = {row["name"] for row in conn.execute("PRAGMA table_info(templates)").fetchall()}
    if "user_id" not in template_columns:
        conn.execute("ALTER TABLE templates ADD COLUMN user_id TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_templates_user ON templates(user_id);")

    # 5. Migrate settings
    settings_columns = {row["name"] for row in conn.execute("PRAGMA table_info(settings)").fetchall()}
    if "user_id" not in settings_columns:
        conn.executescript(
            """
            ALTER TABLE settings RENAME TO settings_old;
            CREATE TABLE settings (
                key TEXT,
                user_id TEXT,
                value TEXT NOT NULL,
                PRIMARY KEY (key, user_id)
            );
            INSERT OR IGNORE INTO settings (key, user_id, value)
            SELECT key, 'default_user', value FROM settings_old;
            DROP TABLE settings_old;
            """
        )

    # 6. Migrate send_log
    send_log_columns = {row["name"] for row in conn.execute("PRAGMA table_info(send_log)").fetchall()}
    if "sender_id" not in send_log_columns:
        conn.execute("ALTER TABLE send_log ADD COLUMN sender_id INTEGER")
    if "sender_email" not in send_log_columns:
        conn.execute("ALTER TABLE send_log ADD COLUMN sender_email TEXT")
    if "user_id" not in send_log_columns:
        conn.execute("ALTER TABLE send_log ADD COLUMN user_id TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_send_log_sender_status ON send_log(sender_id, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_send_log_user ON send_log(user_id)"
    )


def set_setting(conn: sqlite3.Connection, key: str, value: Any, user_id: str = "default_user") -> None:
    conn.execute(
        """
        INSERT INTO settings(key, user_id, value)
        VALUES(?, ?, ?)
        ON CONFLICT(key, user_id) DO UPDATE SET value = excluded.value
        """,
        (key, user_id, json.dumps(value)),
    )
    conn.commit()


def get_setting(conn: sqlite3.Connection, key: str, default: Any = None, user_id: str = "default_user") -> Any:
    row = conn.execute("SELECT value FROM settings WHERE key = ? AND user_id = ?", (key, user_id)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(str(row["value"]))
    except json.JSONDecodeError:
        return row["value"]

