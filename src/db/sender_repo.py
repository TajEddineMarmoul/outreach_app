from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable

from .core import *

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

