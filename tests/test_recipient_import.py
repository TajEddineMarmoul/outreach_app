from __future__ import annotations

import json

import pandas as pd
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

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
                "First_Name": "Sandra",
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
    assert fields["First Name"] == "Sandy"
    assert fields["First_Name"] == "Sandra"
    assert fields["Languages"] == "English, French"
    assert fields["Organization Description"] == "Commerce platform"


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


class _BulkCursor:
    def __init__(self, rows=None, rowcount=0):
        self._rows = rows or []
        self.rowcount = rowcount

    def fetchall(self):
        return self._rows


class _BulkImportConnection:
    supports_bulk_operations = True

    def __init__(self):
        self.executed: list[str] = []
        self.batches: list[tuple[str, list[dict]]] = []
        self.commits = 0

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.executed.append(normalized)
        if normalized.startswith("SELECT * FROM contacts"):
            return _BulkCursor()
        if normalized.startswith("SELECT email FROM do_not_contact"):
            return _BulkCursor()
        if normalized.startswith("UPDATE contacts"):
            return _BulkCursor()
        if normalized.startswith("INSERT INTO campaign_recipients"):
            return _BulkCursor(rowcount=len(params) - 4)
        raise AssertionError(f"Unexpected SQL: {normalized}")

    def executemany(self, sql, params, page_size=500):
        values = list(params)
        self.batches.append((" ".join(sql.split()), values))
        return _BulkCursor(rowcount=len(values))

    def commit(self):
        self.commits += 1


def test_500_recipient_import_uses_batched_database_operations():
    frame = pd.DataFrame(
        [
            {
                "First Name": f"Lead {index}",
                "First_Name": f"Distinct {index}",
                "Email": f"lead{index}@example.com",
            }
            for index in range(500)
        ]
    )
    conn = _BulkImportConnection()

    result = campaigns.import_and_attach_df(
        conn,
        campaign_id=78,
        df=frame,
        mapping={},
        source_type="google_sheet",
        user_id="user-1",
    )

    assert result["imported"] == 500
    assert result["attached"] == 500
    assert conn.commits == 2
    assert len(conn.batches) == 1
    assert len(conn.batches[0][1]) == 500
    assert len(conn.executed) == 4
    custom_fields = json.loads(conn.batches[0][1][0]["custom_fields"])
    assert custom_fields["First Name"] == "Lead 0"
    assert custom_fields["First_Name"] == "Distinct 0"


def test_google_sheet_timeout_returns_a_controlled_http_error(monkeypatch):
    monkeypatch.setattr(campaigns, "require_editable_campaign", lambda *_args: {"id": 78})
    monkeypatch.setattr(
        campaigns,
        "get_public_sheet_csv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.Timeout("slow")),
    )
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(campaigns.router)
    app.dependency_overrides[campaigns.get_db] = lambda: object()
    app.dependency_overrides[campaigns.get_current_user_id] = lambda: "user-1"
    origin = "https://outreach-frontend-166059707324.us-central1.run.app"

    response = TestClient(app).post(
        "/api/campaigns/78/recipients/google-sheet",
        json={
            "url": "https://docs.google.com/spreadsheets/d/example-sheet-id/edit",
            "tab_name": "Sheet1",
            "header_row": 1,
            "mapping": {},
        },
        headers={"Origin": origin},
    )

    assert response.status_code == 504
    assert response.json()["detail"] == "Google Sheets did not respond within 20 seconds"
    assert response.headers["access-control-allow-origin"] == origin
