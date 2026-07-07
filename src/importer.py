from __future__ import annotations

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
        column_mapping=column_mapping,
        source_type=source_type,
        source_url=source_url,
        sheet_id=sheet_id,
        sheet_name=sheet_name,
    )


def import_dataframe(
    frame: pd.DataFrame,
    conn,
    column_mapping: dict[str, str] | None = None,
    source_type: str = "csv",
    source_url: str = "",
    sheet_id: str = "",
    sheet_name: str = "",
) -> ImportResult:
    detected = column_mapping or detect_columns(list(frame.columns))
    result = ImportResult()
    seen_in_file: set[str] = set()

    required_fields = ["email", "first_name", "company_name"]
    missing_columns = [field for field in required_fields if field not in detected]
    if missing_columns:
        result.errors.append(f"Missing required CSV columns: {', '.join(missing_columns)}")
        return result

    for _, row in frame.iterrows():
        email = normalize_email(row.get(detected["email"]))
        if not email:
            result.skipped_missing_email += 1
            continue

        first_name = clean_cell(row.get(detected["first_name"]))
        company_name = clean_cell(row.get(detected["company_name"]))
        if not first_name or not company_name:
            result.skipped_missing_required += 1
            continue

        if email in seen_in_file:
            result.duplicates += 1
            continue
        seen_in_file.add(email)

        keywords = clean_cell(row.get(detected.get("keywords"), ""))
        keyword_1, keyword_2, keyword_3 = extract_keywords(keywords)
        status = ContactStatus.PENDING.value
        if is_do_not_contact(conn, email):
            status = ContactStatus.DO_NOT_CONTACT.value
            result.do_not_contact += 1

        existing = db.fetch_contact_by_email(conn, email)
        if existing:
            last_name = clean_cell(row.get(detected.get("last_name"), ""))
            full_name = clean_cell(row.get(detected.get("full_name"), ""))
            company_website = clean_cell(row.get(detected.get("company_website"), ""))
            linkedin = clean_cell(row.get(detected.get("linkedin"), ""))
            title = clean_cell(row.get(detected.get("title"), ""))
            industry = clean_cell(row.get(detected.get("industry"), ""))
            country = clean_cell(row.get(detected.get("country"), ""))
            
            preview_gen = existing["preview_generated_at"]
            if (existing["keyword_1"] != keyword_1 or 
                existing["keyword_2"] != keyword_2 or 
                existing["keyword_3"] != keyword_3 or 
                existing["company_name"] != company_name or 
                existing["first_name"] != first_name):
                preview_gen = None
                
            conn.execute(
                """
                UPDATE contacts
                SET first_name = ?, last_name = ?, full_name = ?, company_name = ?,
                    company_website = ?, linkedin = ?, title = ?, industry = ?,
                    keywords = ?, keyword_1 = ?, keyword_2 = ?, keyword_3 = ?,
                    country = ?, source_type = ?, source_url = ?, sheet_id = ?,
                    sheet_name = ?, preview_generated_at = ?, last_synced_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    first_name, last_name, full_name, company_name,
                    company_website, linkedin, title, industry,
                    keywords, keyword_1, keyword_2, keyword_3,
                    country, source_type, source_url, sheet_id,
                    sheet_name, preview_gen,
                    db.utcnow_iso() if source_type == "google_sheet" else existing["last_synced_at"],
                    db.utcnow_iso(), existing["id"]
                )
            )
            result.imported += 1
            continue

        inserted = db.insert_contact(
            conn,
            {
                "first_name": first_name,
                "last_name": clean_cell(row.get(detected.get("last_name"), "")),
                "full_name": clean_cell(row.get(detected.get("full_name"), "")),
                "email": email,
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
                "last_synced_at": db.utcnow_iso() if source_type == "google_sheet" else None,
                "status": status,
            },
        )
        if inserted:
            result.imported += 1
        else:
            result.duplicates += 1

    return result


def is_do_not_contact(conn, email: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM do_not_contact WHERE email = ? LIMIT 1",
        (normalize_email(email),),
    ).fetchone()
    return row is not None
