from __future__ import annotations

import json
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd

from . import db
from .models import ContactStatus, ImportResult


COLUMN_ALIASES = {
    "first_name": {"first name", "firstname", "first_name"},
    "last_name": {"last name", "lastname", "last_name"},
    "full_name": {"full name", "fullname", "name", "full_name"},
    "email": {"email", "email address", "work email", "email_address"},
    "company_name": {"company name", "company", "account name", "organization", "company_name"},
    "company_website": {"company website", "website", "company_website"},
    "linkedin": {"linkedin", "linkedin url", "linkedin profile", "person linkedin url"},
    "title": {"title", "job title", "position"},
    "industry": {"industry"},
    "keywords": {"keywords", "keyword"},
    "keyword_1": {"keyword_1", "keyword 1", "keyword1"},
    "keyword_2": {"keyword_2", "keyword 2", "keyword2"},
    "keyword_3": {"keyword_3", "keyword 3", "keyword3"},
    "country": {"country", "location country"},
}


def normalize_column_name(name: str) -> str:
    return " ".join(str(name).strip().replace("_", " ").replace("-", " ").lower().split())


def detect_columns(columns: list[str]) -> dict[str, str]:
    detected: dict[str, str] = {}
    normalized = {normalize_column_name(column): column for column in columns}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                detected[field] = normalized[alias]
                break
    return detected


def clean_cell(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def normalize_email(value: Any) -> str:
    return clean_cell(value).lower()


def extract_keywords(value: Any) -> tuple[str, str, str]:
    raw = clean_cell(value)
    if not raw:
        return "", "", ""
    keywords = [part.strip() for part in raw.split(",") if part.strip()]
    padded = (keywords + ["", "", ""])[:3]
    return padded[0], padded[1], padded[2]


def read_csv(source: str | Path | BinaryIO) -> pd.DataFrame:
    return pd.read_csv(source)


def preview_csv(source: str | Path | BinaryIO) -> tuple[list[str], pd.DataFrame, dict[str, str]]:
    frame = read_csv(source)
    return list(frame.columns), frame.head(10), detect_columns(list(frame.columns))


def import_csv(
    source: str | Path | BinaryIO,
    conn,
    user_id: str,
    column_mapping: dict[str, str] | None = None,
    source_type: str = "csv",
    source_url: str = "",
    sheet_id: str = "",
    sheet_name: str = "",
) -> ImportResult:
    frame = read_csv(source)
    return import_dataframe(
        frame,
        conn,
        user_id=user_id,
        column_mapping=column_mapping,
        source_type=source_type,
        source_url=source_url,
        sheet_id=sheet_id,
        sheet_name=sheet_name,
    )


def import_dataframe(
    frame: pd.DataFrame,
    conn,
    user_id: str,
    column_mapping: dict[str, str] | None = None,
    source_type: str = "csv",
    source_url: str = "",
    sheet_id: str = "",
    sheet_name: str = "",
) -> ImportResult:
    detected = detect_columns(list(frame.columns))
    if column_mapping:
        detected.update(column_mapping)

    result = ImportResult()
    missing_columns = [field for field in ["email"] if field not in detected]
    if missing_columns:
        result.errors.append(f"Missing required CSV columns: {', '.join(missing_columns)}")
        return result

    contacts = _prepare_import_contacts(
        frame,
        detected,
        result,
        source_type=source_type,
        source_url=source_url,
        sheet_id=sheet_id,
        sheet_name=sheet_name,
    )
    if getattr(conn, "supports_bulk_operations", False):
        _import_contacts_bulk(conn, contacts, user_id, result)
    else:
        _import_contacts_rowwise(conn, contacts, user_id, result)
    return result


def _prepare_import_contacts(
    frame: pd.DataFrame,
    detected: dict[str, str],
    result: ImportResult,
    *,
    source_type: str,
    source_url: str,
    sheet_id: str,
    sheet_name: str,
) -> list[dict[str, Any]]:
    contacts: list[dict[str, Any]] = []
    seen_in_file: set[str] = set()
    synced_at = db.utcnow_iso() if source_type == "google_sheet" else None

    for _, row in frame.iterrows():
        email = normalize_email(row.get(detected["email"]))
        if not email:
            result.skipped_missing_email += 1
            continue

        first_name = clean_cell(row.get(detected.get("first_name"), ""))
        company_name = clean_cell(row.get(detected.get("company_name"), ""))

        if email in seen_in_file:
            result.duplicates += 1
            continue
        seen_in_file.add(email)

        keywords = clean_cell(row.get(detected.get("keywords"), ""))
        keyword_1 = clean_cell(row.get(detected.get("keyword_1"), ""))
        keyword_2 = clean_cell(row.get(detected.get("keyword_2"), ""))
        keyword_3 = clean_cell(row.get(detected.get("keyword_3"), ""))
        
        if not keyword_1 and not keyword_2 and not keyword_3:
            keyword_1, keyword_2, keyword_3 = extract_keywords(keywords)
            
        # Preserve headers exactly so similarly named CSV columns stay distinct.
        row_dict: dict[str, str] = {}
        for col in frame.columns:
            cleaned_key = str(col).strip()
            row_dict[cleaned_key] = clean_cell(row.get(col))
        contacts.append(
            {
                "first_name": first_name,
                "last_name": clean_cell(row.get(detected.get("last_name"), "")),
                "full_name": clean_cell(row.get(detected.get("full_name"), "")),
                "email": email,
                "email_normalized": email,
                "company_name": company_name,
                "company_website": clean_cell(row.get(detected.get("company_website"), "")),
                "linkedin": clean_cell(row.get(detected.get("linkedin"), "")),
                "title": clean_cell(row.get(detected.get("title"), "")),
                "industry": clean_cell(row.get(detected.get("industry"), "")),
                "keywords": keywords,
                "keyword_1": keyword_1,
                "keyword_2": keyword_2,
                "keyword_3": keyword_3,
                "country": clean_cell(row.get(detected.get("country"), "")),
                "source_type": source_type,
                "source_url": source_url,
                "sheet_id": sheet_id,
                "sheet_name": sheet_name,
                "last_synced_at": synced_at,
                "custom_fields": json.dumps(row_dict),
            }
        )
    return contacts


def _status_for_import(existing_status: str | None, do_not_contact: bool) -> str:
    if do_not_contact:
        return ContactStatus.DO_NOT_CONTACT.value
    if not existing_status or existing_status == ContactStatus.PENDING.value:
        return ContactStatus.APPROVED.value
    return existing_status


def _updated_contact(contact: dict[str, Any], existing: Any, status: str, user_id: str, now: str) -> dict[str, Any]:
    preview_generated_at = existing["preview_generated_at"]
    preview_fields = ("keyword_1", "keyword_2", "keyword_3", "company_name", "first_name")
    if any(str(existing[field] or "") != str(contact[field] or "") for field in preview_fields):
        preview_generated_at = None

    return {
        **contact,
        "id": existing["id"],
        "user_id": user_id,
        "status": status,
        "preview_generated_at": preview_generated_at,
        "last_synced_at": contact["last_synced_at"] or existing["last_synced_at"],
        "updated_at": now,
    }


def _import_contacts_rowwise(
    conn: Any,
    contacts: list[dict[str, Any]],
    user_id: str,
    result: ImportResult,
) -> None:
    for contact in contacts:
        blocked = is_do_not_contact(conn, contact["email"], user_id)
        if blocked:
            result.do_not_contact += 1
        existing = db.fetch_contact_by_email(conn, contact["email"], user_id)
        status = _status_for_import(existing["status"] if existing else None, blocked)
        if existing:
            values = _updated_contact(contact, existing, status, user_id, db.utcnow_iso())
            conn.execute(_CONTACT_UPDATE_SQL, values)
            result.imported += 1
            continue

        inserted = db.insert_contact(conn, {**contact, "status": status}, user_id)
        if inserted:
            result.imported += 1
        else:
            result.duplicates += 1


def _chunks(values: list[str], size: int = 500):
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def _fetch_existing_contacts_bulk(conn: Any, emails: list[str], user_id: str) -> dict[str, Any]:
    existing: dict[str, Any] = {}
    for chunk in _chunks(emails):
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT * FROM contacts WHERE user_id = ? AND email_normalized IN ({placeholders})",
            [user_id, *chunk],
        ).fetchall()
        existing.update({str(row["email_normalized"]): row for row in rows})
    return existing


def _fetch_do_not_contact_bulk(conn: Any, emails: list[str], user_id: str) -> set[str]:
    blocked: set[str] = set()
    for chunk in _chunks(emails):
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT email FROM do_not_contact WHERE user_id = ? AND email IN ({placeholders})",
            [user_id, *chunk],
        ).fetchall()
        blocked.update(str(row["email"]).strip().lower() for row in rows)
    return blocked


def _import_contacts_bulk(
    conn: Any,
    contacts: list[dict[str, Any]],
    user_id: str,
    result: ImportResult,
) -> None:
    if not contacts:
        return

    emails = [str(contact["email_normalized"]) for contact in contacts]
    existing = _fetch_existing_contacts_bulk(conn, emails, user_id)
    blocked = _fetch_do_not_contact_bulk(conn, emails, user_id)
    result.do_not_contact += len(blocked)
    now = db.utcnow_iso()
    inserts: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []

    for contact in contacts:
        email = str(contact["email_normalized"])
        stored = existing.get(email)
        status = _status_for_import(stored["status"] if stored else None, email in blocked)
        if stored:
            updates.append(_updated_contact(contact, stored, status, user_id, now))
        else:
            inserts.append(
                {
                    **contact,
                    "user_id": user_id,
                    "status": status,
                    "created_at": now,
                    "updated_at": now,
                }
            )

    if updates:
        conn.executemany(_CONTACT_UPDATE_SQL, updates)
    if inserts:
        conn.executemany(_CONTACT_INSERT_SQL, inserts)
    conn.commit()
    result.imported += len(updates) + len(inserts)


_CONTACT_UPDATE_SQL = """
    UPDATE contacts
    SET first_name = :first_name, last_name = :last_name, full_name = :full_name,
        company_name = :company_name, company_website = :company_website,
        linkedin = :linkedin, title = :title, industry = :industry,
        keywords = :keywords, keyword_1 = :keyword_1, keyword_2 = :keyword_2,
        keyword_3 = :keyword_3, country = :country, source_type = :source_type,
        source_url = :source_url, sheet_id = :sheet_id, sheet_name = :sheet_name,
        status = :status, preview_generated_at = :preview_generated_at,
        last_synced_at = :last_synced_at, custom_fields = :custom_fields,
        updated_at = :updated_at
    WHERE id = :id AND user_id = :user_id
"""


_CONTACT_INSERT_SQL = """
    INSERT INTO contacts (
        first_name, last_name, full_name, email, email_normalized, company_name,
        company_website, linkedin, title, industry, keywords, keyword_1,
        keyword_2, keyword_3, country, source_type, source_url, sheet_id,
        sheet_name, last_synced_at, status, custom_fields, created_at, updated_at, user_id
    ) VALUES (
        :first_name, :last_name, :full_name, :email, :email_normalized, :company_name,
        :company_website, :linkedin, :title, :industry, :keywords, :keyword_1,
        :keyword_2, :keyword_3, :country, :source_type, :source_url, :sheet_id,
        :sheet_name, :last_synced_at, :status, :custom_fields, :created_at, :updated_at, :user_id
    )
    ON CONFLICT DO NOTHING
"""


def is_do_not_contact(conn, email: str, user_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM do_not_contact WHERE email = ? AND user_id = ? LIMIT 1",
        (normalize_email(email), user_id),
    ).fetchone()
    return row is not None
