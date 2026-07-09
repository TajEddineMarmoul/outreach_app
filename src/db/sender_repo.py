from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable

from .core import *

def upsert_sender(
    conn: sqlite3.Connection,
    email: str,
    token_path: str,
    user_id: str = "default_user",
    display_name: str = "",
    daily_cap: int = 10,
    status: str = "connected",
    is_default: bool | None = None,
) -> int:
    normalized = email.strip().lower()
    existing = conn.execute("SELECT * FROM senders WHERE email = ? AND user_id = ?", (normalized, user_id)).fetchone()
    if is_default is None:
        is_default = default_sender_id(conn, user_id) is None
    if is_default:
        conn.execute("UPDATE senders SET is_default = 0 WHERE user_id = ?", (user_id,))
    now = utcnow_iso()
    if existing:
        sender_id = int(existing["id"])
        conn.execute(
            """
            UPDATE senders
            SET display_name = ?, token_path = ?, connected_at = ?, status = ?,
                daily_cap = ?, is_default = ?
            WHERE id = ? AND user_id = ?
            """,
            (display_name, token_path, now, status, daily_cap, 1 if is_default else int(existing["is_default"]), sender_id, user_id),
        )
    else:
        cursor = conn.execute(
            """
            INSERT INTO senders(email, display_name, token_path, connected_at, status, daily_cap, is_default, group_name, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (normalized, display_name, token_path, now, status, daily_cap, 1 if is_default else 0, "Default Group", user_id),
        )
        sender_id = int(cursor.lastrowid)
    conn.commit()
    return sender_id


def list_senders(conn: sqlite3.Connection, user_id: str = "default_user", include_removed: bool = False) -> list[sqlite3.Row]:
    if include_removed:
        return list(conn.execute("SELECT * FROM senders WHERE user_id = ? ORDER BY is_default DESC, email", (user_id,)).fetchall())
    return list(
        conn.execute(
            "SELECT * FROM senders WHERE user_id = ? AND status != 'removed' ORDER BY is_default DESC, email",
            (user_id,)
        ).fetchall()
    )


def get_sender(conn: sqlite3.Connection, sender_id: int | None, user_id: str = "default_user") -> sqlite3.Row | None:
    if sender_id is None:
        return None
    return conn.execute("SELECT * FROM senders WHERE id = ? AND user_id = ?", (sender_id, user_id)).fetchone()


def get_sender_by_email(conn: sqlite3.Connection, email: str, user_id: str = "default_user") -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM senders WHERE email = ? AND user_id = ?", (email.strip().lower(), user_id)).fetchone()


def default_sender_id(conn: sqlite3.Connection, user_id: str = "default_user") -> int | None:
    row = conn.execute(
        "SELECT id FROM senders WHERE user_id = ? AND is_default = 1 AND status != 'removed' ORDER BY id LIMIT 1",
        (user_id,)
    ).fetchone()
    if row:
        return int(row["id"])
    row = conn.execute("SELECT id FROM senders WHERE user_id = ? AND status != 'removed' ORDER BY id LIMIT 1", (user_id,)).fetchone()
    return int(row["id"]) if row else None


def get_default_sender(conn: sqlite3.Connection, user_id: str = "default_user") -> sqlite3.Row | None:
    return get_sender(conn, default_sender_id(conn, user_id), user_id)


def set_default_sender(conn: sqlite3.Connection, sender_id: int, user_id: str = "default_user") -> None:
    conn.execute("UPDATE senders SET is_default = 0 WHERE user_id = ?", (user_id,))
    conn.execute("UPDATE senders SET is_default = 1, status = 'connected' WHERE id = ? AND user_id = ?", (sender_id, user_id))
    conn.commit()


def remove_sender(conn: sqlite3.Connection, sender_id: int, user_id: str = "default_user") -> None:
    conn.execute("UPDATE senders SET status = 'removed', is_default = 0 WHERE id = ? AND user_id = ?", (sender_id, user_id))
    conn.execute("UPDATE campaigns SET selected_sender_id = NULL WHERE selected_sender_id = ? AND user_id = ?", (sender_id, user_id))
    conn.commit()


def update_sender(
    conn: sqlite3.Connection,
    sender_id: int,
    user_id: str = "default_user",
    display_name: str = "",
    daily_cap: int = 10,
    group_name: str = "",
) -> None:
    group_name = group_name.strip() if group_name else ""
    if not group_name:
        group_name = "Default Group"
    conn.execute(
        "UPDATE senders SET display_name = ?, daily_cap = ?, group_name = ? WHERE id = ? AND user_id = ?",
        (display_name, daily_cap, group_name, sender_id, user_id),
    )
    conn.commit()


def set_campaign_sender(conn: sqlite3.Connection, campaign_id: int, sender_id: int | None, user_id: str = "default_user") -> None:
    conn.execute(
        "UPDATE campaigns SET selected_sender_id = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (sender_id, utcnow_iso(), campaign_id, user_id),
    )
    conn.commit()


def get_campaign_sender(conn: sqlite3.Connection, campaign_id: int | None, user_id: str = "default_user") -> sqlite3.Row | None:
    if not campaign_id:
        return None
    from src.db.campaign_repo import get_campaign
    campaign = get_campaign(conn, campaign_id, user_id)
    if campaign and campaign["selected_sender_id"]:
        sender = get_sender(conn, int(campaign["selected_sender_id"]), user_id)
        if sender and sender["status"] != "removed":
            return sender
    return None


def update_sender_daily_cap(conn: sqlite3.Connection, sender_id: int, daily_cap: int, user_id: str = "default_user") -> None:
    conn.execute("UPDATE senders SET daily_cap = ? WHERE id = ? AND user_id = ?", (daily_cap, sender_id, user_id))
    conn.commit()
