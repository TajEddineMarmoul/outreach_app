from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd

from . import db
from .importer import normalize_email
from .models import ContactStatus


def add_email(conn, email: str, user_id: str, reason: str = "") -> bool:
    normalized = normalize_email(email)
    if not normalized:
        return False
    conn.execute(
        """
        INSERT INTO do_not_contact(email, user_id, reason, created_at)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(email, user_id) DO UPDATE SET reason = excluded.reason
        """,
        (normalized, user_id, reason, db.utcnow_iso()),
    )
    contact = db.fetch_contact_by_email(conn, normalized, user_id)
    if contact is not None:
        db.set_contact_status(conn, int(contact["id"]), ContactStatus.DO_NOT_CONTACT.value, user_id)
    conn.commit()
    return True


def remove_email(conn, email: str, user_id: str) -> None:
    conn.execute("DELETE FROM do_not_contact WHERE email = ? AND user_id = ?", (normalize_email(email), user_id))
    conn.commit()


def is_blocked(conn, email: str, user_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM do_not_contact WHERE email = ? AND user_id = ? LIMIT 1",
        (normalize_email(email), user_id),
    ).fetchone()
    return row is not None


def import_dnc_csv(conn, source: str | Path | BinaryIO, user_id: str, reason: str = "Imported DNC") -> int:
    frame = pd.read_csv(source)
    if frame.empty:
        return 0
    email_column = None
    for column in frame.columns:
        if str(column).strip().lower() in {"email", "email address", "work email"}:
            email_column = column
            break
    if email_column is None:
        email_column = frame.columns[0]

    added = 0
    for value in frame[email_column].tolist():
        if add_email(conn, str(value), user_id, reason):
            added += 1
    return added


def rows(conn, user_id: str) -> list:
    return list(conn.execute("SELECT * FROM do_not_contact WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall())
