from __future__ import annotations

from pathlib import Path

from src import importer
from src.importer import extract_keywords
from src.models import ContactStatus


def test_csv_import_deduplicates_missing_email_and_extracts_keywords(tmp_path: Path, monkeypatch) -> None:
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
    inserted: dict = {}
    monkeypatch.setattr(importer, "is_do_not_contact", lambda *_args: False)
    monkeypatch.setattr(importer.db, "fetch_contact_by_email", lambda *_args: None)

    def fake_insert(_conn, contact, user_id):
        inserted.update(contact)
        inserted["user_id"] = user_id
        return True

    monkeypatch.setattr(importer.db, "insert_contact", fake_insert)

    result = importer.import_csv(csv_path, object(), user_id="test_user")

    assert result.imported == 1
    assert result.skipped_missing_email == 1
    assert result.duplicates == 1
    assert inserted["email"] == "alice@example.com"
    assert inserted["status"] == ContactStatus.APPROVED.value
    assert inserted["keyword_1"] == "plant-based drinks"
    assert inserted["keyword_2"] == "farm transition"
    assert inserted["keyword_3"] == "dairy alternatives"


def test_keyword_extraction_handles_short_and_empty_values() -> None:
    assert extract_keywords("one, two") == ("one", "two", "")
    assert extract_keywords("") == ("", "", "")
