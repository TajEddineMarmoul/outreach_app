from __future__ import annotations

from pathlib import Path

from src import db
from src.importer import extract_keywords, import_csv
from src.models import ContactStatus


def test_csv_import_deduplicates_missing_email_and_extracts_keywords(tmp_path: Path) -> None:
    conn = db.init_db(tmp_path / "outreach.db")
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text(
        "\n".join(
            [
                "First Name,Last Name,Company Name,Email,Keywords,Country",
                "Alice,A,Plant Co,ALICE@EXAMPLE.COM,\"plant-based drinks, farm transition, dairy alternatives, recipe development\",France",
                "Bob,B,Boom Co,,\"ai, data\",France",
                "Alice,A,Plant Co,alice@example.com,\"duplicate\",France",
            ]
        ),
        encoding="utf-8",
    )

    result = import_csv(csv_path, conn, user_id="test_user")

    assert result.imported == 1
    assert result.skipped_missing_email == 1
    assert result.duplicates == 1
    contact = db.fetch_contact_by_email(conn, "alice@example.com", user_id="test_user")
    assert contact is not None
    assert contact["email"] == "alice@example.com"
    assert contact["status"] == ContactStatus.PENDING.value
    assert contact["keyword_1"] == "plant-based drinks"
    assert contact["keyword_2"] == "farm transition"
    assert contact["keyword_3"] == "dairy alternatives"


def test_keyword_extraction_handles_short_and_empty_values() -> None:
    assert extract_keywords("one, two") == ("one", "two", "")
    assert extract_keywords("") == ("", "", "")
