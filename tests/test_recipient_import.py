from __future__ import annotations

import json

import pandas as pd

from api.routers import campaigns
from src import importer
from src.db.contact_repo import add_campaign_recipients
from src.models import ContactStatus, ImportResult


def test_import_and_attach_auto_detects_email_column(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "First Name": "Sandy",
                "Company Name": "Shopify",
                "Email": "TEST@example.com",
                "Languages": "English, French",
            }
        ]
    )
    captured: dict = {}

    def fake_import_dataframe(_frame, _conn, **kwargs):
        captured["mapping"] = kwargs["column_mapping"]
        return ImportResult(imported=1)

    def fake_attach(_conn, campaign_id, emails, user_id):
        captured["attachment"] = (campaign_id, emails, user_id)
        return 1

    monkeypatch.setattr(campaigns, "import_dataframe", fake_import_dataframe)
    monkeypatch.setattr(campaigns.db, "add_campaign_recipients_by_emails", fake_attach)

    result = campaigns.import_and_attach_df(
        object(),
        campaign_id=21,
        df=frame,
        mapping={},
        source_type="csv",
        user_id="user-1",
    )

    assert captured["mapping"]["email"] == "Email"
    assert captured["attachment"] == (21, ["test@example.com"], "user-1")
    assert result["attached"] == 1


def test_imported_contacts_are_approved_and_keep_every_csv_field(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "First Name": "Sandy",
                "Email": "sandy@example.com",
                "Languages": "English, French",
                "Organization Description": "Commerce platform",
            }
        ]
    )
    inserted: dict = {}

    monkeypatch.setattr(importer, "is_do_not_contact", lambda *_args: False)
    monkeypatch.setattr(importer.db, "fetch_contact_by_email", lambda *_args: None)

    def fake_insert(_conn, contact, user_id):
        inserted.update(contact)
        inserted["user_id"] = user_id
        return True

    monkeypatch.setattr(importer.db, "insert_contact", fake_insert)

    result = importer.import_dataframe(frame, object(), user_id="user-1")

    fields = json.loads(inserted["custom_fields"])
    assert result.imported == 1
    assert inserted["status"] == ContactStatus.APPROVED.value
    assert fields["First_Name"] == "Sandy"
    assert fields["Languages"] == "English, French"
    assert fields["Organization_Description"] == "Commerce platform"


class _Cursor:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _RecipientConnection:
    def __init__(self, contact_status: str):
        self.contact_status = contact_status
        self.inserted_status: str | None = None

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT status FROM contacts"):
            return _Cursor({"status": self.contact_status})
        if normalized.startswith("SELECT 1 FROM campaign_recipients"):
            return _Cursor(None)
        if normalized.startswith("INSERT INTO campaign_recipients"):
            self.inserted_status = params[2]
            return _Cursor()
        raise AssertionError(f"Unexpected SQL: {normalized}")

    def commit(self):
        return None


def test_previously_sent_contact_is_approved_for_a_new_campaign():
    conn = _RecipientConnection(ContactStatus.SENT.value)

    attached = add_campaign_recipients(conn, campaign_id=42, contact_ids=[7])

    assert attached == 1
    assert conn.inserted_status == ContactStatus.APPROVED.value
