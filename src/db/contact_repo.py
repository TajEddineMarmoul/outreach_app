from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable

from .core import *

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

