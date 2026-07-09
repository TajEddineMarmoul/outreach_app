from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable

from .core import *

def seed_default_campaign(conn: sqlite3.Connection, user_id: str = "default_user") -> None:
    exists = conn.execute("SELECT id FROM campaigns WHERE user_id = ? ORDER BY id LIMIT 1", (user_id,)).fetchone()
    if exists:
        return
    now = utcnow_iso()
    conn.execute(
        """
        INSERT INTO campaigns
            (name, subject_template, body_template, fallback_body_template,
             attachment_path, status, created_at, updated_at, user_id)
        VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?)
        """,
        (
            "Test Campaign",
            DEFAULT_SUBJECT_TEMPLATE,
            DEFAULT_BODY_TEMPLATE,
            DEFAULT_FALLBACK_BODY_TEMPLATE,
            "data/uploads/resume.pdf",
            now,
            now,
            user_id,
        ),
    )
    conn.commit()


def get_default_campaign(conn: sqlite3.Connection, user_id: str = "default_user") -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM campaigns WHERE user_id = ? ORDER BY id LIMIT 1", (user_id,)).fetchone()


def create_campaign(conn: sqlite3.Connection, user_id: str = "default_user", name: str = "Untitled campaign") -> int:
    now = utcnow_iso()
    cursor = conn.execute(
        """
        INSERT INTO campaigns
            (name, subject_template, body_template, fallback_body_template,
             attachment_path, selected_sender_id, status, created_at, updated_at, user_id)
        VALUES (?, '', '', '', '', NULL, 'draft', ?, ?, ?)
        """,
        (
            name,
            now,
            now,
            user_id,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_campaign(conn: sqlite3.Connection, campaign_id: int, user_id: str = "default_user") -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user_id)).fetchone()


def list_campaigns(conn: sqlite3.Connection, user_id: str = "default_user") -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM campaigns WHERE user_id = ? ORDER BY created_at DESC, id DESC", (user_id,)).fetchall())


def update_campaign(
    conn: sqlite3.Connection,
    campaign_id: int,
    user_id: str = "default_user",
    subject_template: str = "",
    body_template: str = "",
    fallback_body_template: str = "",
    attachment_path: str = "",
) -> None:
    now = utcnow_iso()
    conn.execute(
        """
        UPDATE campaigns
        SET subject_template = ?, body_template = ?, fallback_body_template = ?,
            attachment_path = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (
            subject_template,
            body_template,
            fallback_body_template,
            attachment_path,
            now,
            campaign_id,
            user_id,
        ),
    )
    conn.commit()


def update_campaign_name(conn: sqlite3.Connection, campaign_id: int, user_id: str = "default_user", name: str = "") -> None:
    conn.execute(
        "UPDATE campaigns SET name = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (name, utcnow_iso(), campaign_id, user_id),
    )
    conn.commit()


def set_campaign_status(conn: sqlite3.Connection, status: str, campaign_id: int | None = None, user_id: str = "default_user") -> None:
    if campaign_id is None:
        campaign = get_default_campaign(conn, user_id)
        if not campaign:
            return
        final_id = int(campaign["id"])
    else:
        final_id = campaign_id
    conn.execute(
        "UPDATE campaigns SET status = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (status, utcnow_iso(), final_id, user_id),
    )
    conn.commit()


def get_campaign_status(conn: sqlite3.Connection, campaign_id: int | None = None, user_id: str = "default_user") -> str:
    if campaign_id is None:
        campaign = get_default_campaign(conn, user_id)
        return str(campaign["status"]) if campaign else "stopped"
    row = conn.execute("SELECT status FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user_id)).fetchone()
    return str(row["status"]) if row else "stopped"


def delete_campaign(conn: sqlite3.Connection, campaign_id: int, user_id: str = "default_user") -> None:
    conn.execute("DELETE FROM send_log WHERE campaign_id = ? AND user_id = ?", (campaign_id, user_id))
    conn.execute("DELETE FROM settings WHERE key LIKE ? AND user_id = ?", (f"campaign_{campaign_id}_%", user_id))
    conn.execute("DELETE FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user_id))
    conn.commit()


# ── Templates ──

def get_templates(conn: sqlite3.Connection, user_id: str = "default_user") -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM templates WHERE user_id = ? ORDER BY id", (user_id,)).fetchall())

def create_template(conn: sqlite3.Connection, user_id: str = "default_user", title: str = "", subject: str = "", body: str = "") -> int:
    conn.execute(
        "INSERT INTO templates (title, subject, body, user_id) VALUES (?, ?, ?, ?)",
        (title, subject, body, user_id),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

def delete_template(conn: sqlite3.Connection, template_id: int, user_id: str = "default_user") -> None:
    conn.execute("DELETE FROM templates WHERE id = ? AND user_id = ?", (template_id, user_id))
    conn.commit()
