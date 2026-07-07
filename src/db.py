from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import (
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


def seed_default_campaign(conn: sqlite3.Connection) -> None:
    exists = conn.execute("SELECT id FROM campaigns ORDER BY id LIMIT 1").fetchone()
    if exists:
        return
    now = utcnow_iso()
    conn.execute(
        """
        INSERT INTO campaigns
            (name, subject_template, body_template, fallback_body_template,
             attachment_path, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
        """,
        (
            "Test Campaign",
            DEFAULT_SUBJECT_TEMPLATE,
            DEFAULT_BODY_TEMPLATE,
            DEFAULT_FALLBACK_BODY_TEMPLATE,
            "data/uploads/resume.pdf",
            now,
            now,
        ),
    )
    conn.commit()


def get_default_campaign(conn: sqlite3.Connection) -> sqlite3.Row:
    return conn.execute("SELECT * FROM campaigns ORDER BY id LIMIT 1").fetchone()


def create_campaign(conn: sqlite3.Connection, name: str = "Untitled campaign") -> int:
    now = utcnow_iso()
    cursor = conn.execute(
        """
        INSERT INTO campaigns
            (name, subject_template, body_template, fallback_body_template,
             attachment_path, selected_sender_id, status, created_at, updated_at)
        VALUES (?, '', '', '', '', NULL, 'draft', ?, ?)
        """,
        (
            name,
            now,
            now,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_campaign(conn: sqlite3.Connection, campaign_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()


def list_campaigns(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM campaigns ORDER BY created_at DESC, id DESC").fetchall())


def upsert_sender(
    conn: sqlite3.Connection,
    email: str,
    token_path: str,
    display_name: str = "",
    daily_cap: int = 10,
    status: str = "connected",
    is_default: bool | None = None,
) -> int:
    normalized = email.strip().lower()
    existing = conn.execute("SELECT * FROM senders WHERE email = ?", (normalized,)).fetchone()
    if is_default is None:
        is_default = default_sender_id(conn) is None
    if is_default:
        conn.execute("UPDATE senders SET is_default = 0")
    now = utcnow_iso()
    if existing:
        sender_id = int(existing["id"])
        conn.execute(
            """
            UPDATE senders
            SET display_name = ?, token_path = ?, connected_at = ?, status = ?,
                daily_cap = ?, is_default = ?
            WHERE id = ?
            """,
            (display_name, token_path, now, status, daily_cap, 1 if is_default else int(existing["is_default"]), sender_id),
        )
    else:
        cursor = conn.execute(
            """
            INSERT INTO senders(email, display_name, token_path, connected_at, status, daily_cap, is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (normalized, display_name, token_path, now, status, daily_cap, 1 if is_default else 0),
        )
        sender_id = int(cursor.lastrowid)
    conn.commit()
    return sender_id


def list_senders(conn: sqlite3.Connection, include_removed: bool = False) -> list[sqlite3.Row]:
    if include_removed:
        return list(conn.execute("SELECT * FROM senders ORDER BY is_default DESC, email").fetchall())
    return list(
        conn.execute(
            "SELECT * FROM senders WHERE status != 'removed' ORDER BY is_default DESC, email"
        ).fetchall()
    )


def get_sender(conn: sqlite3.Connection, sender_id: int | None) -> sqlite3.Row | None:
    if sender_id is None:
        return None
    return conn.execute("SELECT * FROM senders WHERE id = ?", (sender_id,)).fetchone()


def get_sender_by_email(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM senders WHERE email = ?", (email.strip().lower(),)).fetchone()


def default_sender_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT id FROM senders WHERE is_default = 1 AND status != 'removed' ORDER BY id LIMIT 1"
    ).fetchone()
    if row:
        return int(row["id"])
    row = conn.execute("SELECT id FROM senders WHERE status != 'removed' ORDER BY id LIMIT 1").fetchone()
    return int(row["id"]) if row else None


def get_default_sender(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return get_sender(conn, default_sender_id(conn))


def set_default_sender(conn: sqlite3.Connection, sender_id: int) -> None:
    conn.execute("UPDATE senders SET is_default = 0")
    conn.execute("UPDATE senders SET is_default = 1, status = 'connected' WHERE id = ?", (sender_id,))
    conn.commit()


def remove_sender(conn: sqlite3.Connection, sender_id: int) -> None:
    conn.execute("UPDATE senders SET status = 'removed', is_default = 0 WHERE id = ?", (sender_id,))
    conn.execute("UPDATE campaigns SET selected_sender_id = NULL WHERE selected_sender_id = ?", (sender_id,))
    conn.commit()


def update_sender(
    conn: sqlite3.Connection,
    sender_id: int,
    display_name: str,
    daily_cap: int,
    group_name: str,
) -> None:
    conn.execute(
        "UPDATE senders SET display_name = ?, daily_cap = ?, group_name = ? WHERE id = ?",
        (display_name, daily_cap, group_name, sender_id),
    )
    conn.commit()


def set_campaign_sender(conn: sqlite3.Connection, campaign_id: int, sender_id: int | None) -> None:
    conn.execute(
        "UPDATE campaigns SET selected_sender_id = ?, updated_at = ? WHERE id = ?",
        (sender_id, utcnow_iso(), campaign_id),
    )
    conn.commit()


def get_campaign_sender(conn: sqlite3.Connection, campaign_id: int | None) -> sqlite3.Row | None:
    if not campaign_id:
        return None
    campaign = get_campaign(conn, campaign_id)
    if campaign and campaign["selected_sender_id"]:
        sender = get_sender(conn, int(campaign["selected_sender_id"]))
        if sender and sender["status"] != "removed":
            return sender
    return None


def update_sender_daily_cap(conn: sqlite3.Connection, sender_id: int, daily_cap: int) -> None:
    conn.execute("UPDATE senders SET daily_cap = ? WHERE id = ?", (daily_cap, sender_id))
    conn.commit()


def update_campaign(
    conn: sqlite3.Connection,
    campaign_id: int,
    subject_template: str,
    body_template: str,
    fallback_body_template: str,
    attachment_path: str,
) -> None:
    now = utcnow_iso()
    conn.execute(
        """
        UPDATE campaigns
        SET subject_template = ?, body_template = ?, fallback_body_template = ?,
            attachment_path = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            subject_template,
            body_template,
            fallback_body_template,
            attachment_path,
            now,
            campaign_id,
        ),
    )
    conn.commit()


def update_campaign_name(conn: sqlite3.Connection, campaign_id: int, name: str) -> None:
    conn.execute(
        "UPDATE campaigns SET name = ?, updated_at = ? WHERE id = ?",
        (name, utcnow_iso(), campaign_id),
    )
    conn.commit()


def set_campaign_status(conn: sqlite3.Connection, status: str, campaign_id: int | None = None) -> None:
    campaign = get_default_campaign(conn) if campaign_id is None else None
    final_id = campaign_id or int(campaign["id"])
    conn.execute(
        "UPDATE campaigns SET status = ?, updated_at = ? WHERE id = ?",
        (status, utcnow_iso(), final_id),
    )
    conn.commit()


def get_campaign_status(conn: sqlite3.Connection, campaign_id: int | None = None) -> str:
    if campaign_id is None:
        return str(get_default_campaign(conn)["status"])
    row = conn.execute("SELECT status FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
    return str(row["status"]) if row else "stopped"


def insert_contact(conn: sqlite3.Connection, contact: dict[str, Any]) -> bool:
    now = utcnow_iso()
    data = {
        "first_name": "",
        "last_name": "",
        "full_name": "",
        "email": "",
        "company_name": "",
        "company_website": "",
        "linkedin": "",
        "title": "",
        "industry": "",
        "keywords": "",
        "keyword_1": "",
        "keyword_2": "",
        "keyword_3": "",
        "country": "",
        "source_type": "csv",
        "source_url": "",
        "sheet_id": "",
        "sheet_name": "",
        "last_synced_at": None,
        "status": ContactStatus.PENDING.value,
        "custom_fields": "{}",
        **contact,
        "created_at": now,
        "updated_at": now,
    }
    try:
        conn.execute(
            """
            INSERT INTO contacts (
                first_name, last_name, full_name, email, company_name,
                company_website, linkedin, title, industry, keywords,
                keyword_1, keyword_2, keyword_3, country, source_type,
                source_url, sheet_id, sheet_name, last_synced_at, status,
                custom_fields, created_at, updated_at
            )
            VALUES (
                :first_name, :last_name, :full_name, :email, :company_name,
                :company_website, :linkedin, :title, :industry, :keywords,
                :keyword_1, :keyword_2, :keyword_3, :country, :source_type,
                :source_url, :sheet_id, :sheet_name, :last_synced_at, :status,
                :custom_fields, :created_at, :updated_at
            )
            """,
            data,
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def fetch_contacts(
    conn: sqlite3.Connection,
    statuses: Iterable[str] | None = None,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM contacts"
    params: list[Any] = []
    if statuses:
        values = list(statuses)
        placeholders = ",".join("?" for _ in values)
        sql += f" WHERE status IN ({placeholders})"
        params.extend(values)
    sql += " ORDER BY id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return list(conn.execute(sql, params).fetchall())


def add_campaign_recipients(
    conn: sqlite3.Connection,
    campaign_id: int,
    contact_ids: Iterable[int],
) -> int:
    now = utcnow_iso()
    before = conn.total_changes
    conn.executemany(
        """
        INSERT OR IGNORE INTO campaign_recipients(campaign_id, contact_id, created_at)
        VALUES (?, ?, ?)
        """,
        [(campaign_id, int(contact_id), now) for contact_id in contact_ids],
    )
    conn.commit()
    return conn.total_changes - before


def add_campaign_recipients_by_emails(
    conn: sqlite3.Connection,
    campaign_id: int,
    emails: Iterable[str],
) -> int:
    contact_ids: list[int] = []
    for email in emails:
        contact = fetch_contact_by_email(conn, email)
        if contact:
            contact_ids.append(int(contact["id"]))
    return add_campaign_recipients(conn, campaign_id, contact_ids)


def campaign_contacts(
    conn: sqlite3.Connection,
    campaign_id: int,
    statuses: Iterable[str] | None = None,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    sql = """
        SELECT c.*
        FROM contacts c
        INNER JOIN campaign_recipients cr ON cr.contact_id = c.id
        WHERE cr.campaign_id = ?
    """
    params: list[Any] = [campaign_id]
    if statuses:
        values = list(statuses)
        placeholders = ",".join("?" for _ in values)
        sql += f" AND c.status IN ({placeholders})"
        params.extend(values)
    sql += " ORDER BY c.id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return list(conn.execute(sql, params).fetchall())


def campaign_contact_count(conn: sqlite3.Connection, campaign_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM campaign_recipients WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()
    return int(row["count"])


def campaign_sent_count(conn: sqlite3.Connection, campaign_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM send_log WHERE campaign_id = ? AND status = 'sent'",
        (campaign_id,),
    ).fetchone()
    return int(row["count"])


def campaign_stats(conn: sqlite3.Connection, campaign_id: int) -> dict[str, int]:
    return {
        "recipients": campaign_contact_count(conn, campaign_id),
        "sent": campaign_sent_count(conn, campaign_id),
    }


def fetch_contact(conn: sqlite3.Connection, contact_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()


def fetch_contact_by_email(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM contacts WHERE email = ?", (email.lower().strip(),)).fetchone()


def set_contact_status(conn: sqlite3.Connection, contact_id: int, status: str) -> None:
    conn.execute(
        "UPDATE contacts SET status = ?, updated_at = ? WHERE id = ?",
        (status, utcnow_iso(), contact_id),
    )
    conn.commit()


def set_contacts_status(conn: sqlite3.Connection, contact_ids: Iterable[int], status: str) -> int:
    ids = list(contact_ids)
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"UPDATE contacts SET status = ?, updated_at = ? WHERE id IN ({placeholders})",
        [status, utcnow_iso(), *ids],
    )
    conn.commit()
    return conn.total_changes


def mark_preview_generated(
    conn: sqlite3.Connection,
    contact_id: int,
    subject: str,
    body: str,
) -> None:
    now = utcnow_iso()
    conn.execute(
        """
        UPDATE contacts
        SET preview_generated_at = ?, last_preview_subject = ?, last_preview_body = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (now, subject, body, now, contact_id),
    )
    conn.commit()


def clear_campaign_previews(conn: sqlite3.Connection, campaign_id: int) -> None:
    conn.execute(
        """
        UPDATE contacts
        SET preview_generated_at = NULL,
            last_preview_subject = NULL,
            last_preview_body = NULL,
            updated_at = ?
        WHERE id IN (
            SELECT contact_id
            FROM campaign_recipients
            WHERE campaign_id = ?
        )
        """,
        (utcnow_iso(), campaign_id),
    )
    conn.commit()


def count_contacts_by_status(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {status: 0 for status in STATUS_VALUES}
    rows = conn.execute("SELECT status, COUNT(*) AS count FROM contacts GROUP BY status").fetchall()
    for row in rows:
        counts[str(row["status"])] = int(row["count"])
    counts["total"] = sum(counts.values())
    return counts


def sent_today_count(conn: sqlite3.Connection, today_prefix: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM send_log
        WHERE status = 'sent' AND sent_at LIKE ?
        """,
        (f"{today_prefix}%",),
    ).fetchone()
    return int(row["count"])


def first_successful_send_date(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT MIN(sent_at) AS first_sent_at FROM send_log WHERE status = 'sent'"
    ).fetchone()
    return str(row["first_sent_at"]) if row and row["first_sent_at"] else None


def last_successful_send_at(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT MAX(sent_at) AS last_sent_at FROM send_log WHERE status = 'sent'"
    ).fetchone()
    return str(row["last_sent_at"]) if row and row["last_sent_at"] else None


def has_send_attempt(conn: sqlite3.Connection, contact_id: int) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM send_log
        WHERE contact_id = ? AND status IN ('attempting', 'sent')
        LIMIT 1
        """,
        (contact_id,),
    ).fetchone()
    return row is not None


def create_send_attempt(
    conn: sqlite3.Connection,
    contact_id: int | None,
    campaign_id: int | None,
    recipient_email: str,
    subject: str,
    body: str,
    attachment_name: str,
    status: str = "attempting",
    sender_id: int | None = None,
    sender_email: str | None = None,
) -> int:
    now = utcnow_iso()
    cursor = conn.execute(
        """
        INSERT INTO send_log (
            contact_id, campaign_id, recipient_email, subject, body_snapshot,
            sent_at, status, error_message, gmail_message_id, gmail_thread_id,
            sender_id, sender_email, attachment_name, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, NULL, ?, NULL, NULL, NULL, ?, ?, ?, ?, ?)
        """,
        (
            contact_id,
            campaign_id,
            recipient_email,
            subject,
            body,
            status,
            sender_id,
            sender_email,
            attachment_name,
            now,
            now,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def update_send_log(
    conn: sqlite3.Connection,
    log_id: int,
    status: str,
    error_message: str | None = None,
    gmail_message_id: str | None = None,
    gmail_thread_id: str | None = None,
    sent_at: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE send_log
        SET status = ?, error_message = ?, gmail_message_id = ?,
            gmail_thread_id = ?, sent_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            error_message,
            gmail_message_id,
            gmail_thread_id,
            sent_at,
            utcnow_iso(),
            log_id,
        ),
    )
    conn.commit()


def recent_send_errors(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT *
            FROM send_log
            WHERE status IN ('failed', 'sent')
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    )


def bounce_rate_percent(conn: sqlite3.Connection) -> float:
    counts = count_contacts_by_status(conn)
    sent_or_bounced = counts.get(ContactStatus.SENT.value, 0) + counts.get(ContactStatus.BOUNCED.value, 0)
    if sent_or_bounced == 0:
        return 0.0
    return (counts.get(ContactStatus.BOUNCED.value, 0) / sent_or_bounced) * 100


def sender_send_log_rows(conn: sqlite3.Connection, sender_id: int) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM send_log WHERE sender_id = ? ORDER BY created_at DESC",
            (sender_id,),
        ).fetchall()
    )


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


def send_log_rows(conn: sqlite3.Connection, campaign_id: int | None = None) -> list[sqlite3.Row]:
    if campaign_id is None:
        return list(conn.execute("SELECT * FROM send_log ORDER BY created_at DESC").fetchall())
    return list(
        conn.execute(
            "SELECT * FROM send_log WHERE campaign_id = ? ORDER BY created_at DESC",
            (campaign_id,),
        ).fetchall()
    )


def contact_rows_with_last_log(
    conn: sqlite3.Connection,
    campaign_id: int | None = None,
) -> list[sqlite3.Row]:
    campaign_join = ""
    campaign_where = ""
    params: list[Any] = []
    if campaign_id is not None:
        campaign_join = "INNER JOIN campaign_recipients cr ON cr.contact_id = c.id"
        campaign_where = "WHERE cr.campaign_id = ?"
        params.append(campaign_id)
    return list(
        conn.execute(
            f"""
            SELECT
                c.*,
                latest.sent_at AS last_sent_at,
                latest.error_message AS last_error_message
            FROM contacts c
            {campaign_join}
            LEFT JOIN (
                SELECT sl.*
                FROM send_log sl
                INNER JOIN (
                    SELECT contact_id, MAX(created_at) AS max_created_at
                    FROM send_log
                    WHERE contact_id IS NOT NULL
                    GROUP BY contact_id
                ) latest_ids
                    ON latest_ids.contact_id = sl.contact_id
                   AND latest_ids.max_created_at = sl.created_at
            ) latest ON latest.contact_id = c.id
            {campaign_where}
            ORDER BY c.id
            """,
            params,
        ).fetchall()
    )


def delete_campaign(conn: sqlite3.Connection, campaign_id: int) -> None:
    conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    conn.commit()


# ── Templates ──

def get_templates(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM templates ORDER BY id").fetchall())

def create_template(conn: sqlite3.Connection, title: str, subject: str, body: str) -> int:
    conn.execute(
        "INSERT INTO templates (title, subject, body) VALUES (?, ?, ?)",
        (title, subject, body),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

def delete_template(conn: sqlite3.Connection, template_id: int) -> None:
    conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    conn.commit()

