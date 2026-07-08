from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable

from .core import *

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

