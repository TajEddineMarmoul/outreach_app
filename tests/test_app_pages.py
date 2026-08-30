from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sqlite3

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from api.main import app
from api.auth import get_current_user_id
from api.routers import analytics as analytics_router, contacts, templates
from api.schemas import TemplateCreate
from src.platform.db import get_session
from src.platform.models import Base, SendLog
from src.platform.services import ensure_user
from src.models import ImportResult
from src.db.campaign_repo import create_campaign


def test_created_campaign_id_is_read_before_releasing_pooled_connection():
    class Connection:
        committed = False
        def execute(self, *args):
            return self
        @property
        def lastrowid(self):
            assert not self.committed, "A pool may assign a different connection after commit"
            return 42
        def commit(self):
            self.committed = True
    conn = Connection()
    assert create_campaign(conn, "owner", "Campaign") == 42 and conn.committed


@pytest.fixture
def connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE contacts (id INTEGER PRIMARY KEY, user_id TEXT, email_normalized TEXT, first_name TEXT, last_name TEXT, company_name TEXT, custom_fields TEXT, status TEXT);
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY, user_id TEXT);
        CREATE TABLE campaign_recipients (campaign_id INTEGER, contact_id INTEGER);
        CREATE TABLE templates (id INTEGER PRIMARY KEY, user_id TEXT, title TEXT, subject TEXT, body TEXT, updated_at TEXT);
    """)
    yield conn
    conn.close()


def test_contacts_pagination_search_and_group_ownership(connection):
    for index in range(8):
        connection.execute("INSERT INTO contacts VALUES (?, 'owner', ?, ?, '', 'Acme', '{}', 'approved')", (index + 1, f"person{index}@example.test", f"Person {index}"))
    connection.execute("INSERT INTO contacts VALUES (99, 'other', 'private@example.test', 'Private', '', 'Acme', '{}', 'approved')")
    connection.execute("INSERT INTO campaigns VALUES (1, 'owner'), (2, 'other')")
    connection.execute("INSERT INTO campaign_recipients VALUES (1, 1), (1, 8), (2, 99)")
    result = contacts.contact_library(search="", campaign_id=None, page=2, page_size=6, conn=connection, user_id="owner")
    assert result["total"] == 8 and [item["id"] for item in result["items"]] == [2, 1]
    result = contacts.contact_library(search="person 7", campaign_id=1, page=1, page_size=6, conn=connection, user_id="owner")
    assert result["total"] == 1 and result["items"][0]["id"] == 8
    with pytest.raises(HTTPException) as exc:
        contacts.contact_library(search="", campaign_id=2, page=1, page_size=6, conn=connection, user_id="owner")
    assert exc.value.status_code == 404


def test_manual_contact_returns_import_result_and_preserves_existing(monkeypatch):
    monkeypatch.setattr(contacts.db, "fetch_contact_by_email", lambda *_: None)
    monkeypatch.setattr(contacts, "is_do_not_contact", lambda *_: False)
    seen = []
    def import_frame(frame, conn, user_id, **kwargs):
        seen.append((frame.iloc[0].to_dict(), user_id, kwargs))
        return ImportResult(imported=1)
    monkeypatch.setattr(contacts, "import_dataframe", import_frame)
    result = contacts.create_contact(contacts.ContactCreate(email="TEST@example.test", company="O’Neil"), object(), "owner")
    assert result["imported"] == 1 and result["status"] == "success"
    assert seen[0][0]["email"] == "test@example.test" and seen[0][0]["company"] == "O’Neil"
    monkeypatch.setattr(contacts.db, "fetch_contact_by_email", lambda *_: {"id": 1})
    with pytest.raises(HTTPException) as exc:
        contacts.create_contact(contacts.ContactCreate(email="test@example.test"), object(), "owner")
    assert exc.value.status_code == 409 and len(seen) == 1


def test_templates_edit_only_the_owners_record_and_record_date(connection):
    connection.execute("INSERT INTO templates VALUES (1, 'owner', 'Old', 'Old subject', 'Old body', NULL)")
    request = TemplateCreate(title="Updated", subject="Hello {{company}}", body="A reusable message")
    with pytest.raises(HTTPException) as exc:
        templates.update_template(1, request, connection, "other")
    assert exc.value.status_code == 404
    templates.update_template(1, request, connection, "owner")
    row = connection.execute("SELECT * FROM templates WHERE id = 1").fetchone()
    assert row["title"] == "Updated" and row["updated_at"] and row["body"] == request.body
    with pytest.raises(HTTPException):
        templates.update_template(1, TemplateCreate(title=" ", subject="S", body="B"), connection, "owner")


def test_analytics_counts_all_pages_excludes_simulations_and_isolates_users(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'analytics.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    now = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(analytics_router, "utcnow", lambda: now)
    with Session(engine) as session:
        ensure_user(session, "owner")
        ensure_user(session, "other")
        for index in range(8):
            session.add(SendLog(user_id="owner", recipient_email=f"person{index}@example.test", subject="=1+1", status="sent", created_at=now - timedelta(hours=1)))
        for user, status, time in [("owner", "failed", now), ("owner", "test_sent", now), ("owner", "attempting", now), ("other", "sent", now), ("owner", "sent", now - timedelta(days=31)), ("owner", "sent", now + timedelta(days=1))]:
            session.add(SendLog(user_id=user, recipient_email="example@example.test", status=status, created_at=time))
        session.commit()
        result = analytics_router.analytics(days=7, page=2, session=session, user_id="owner")
        assert (result["attempts"], result["sent"], result["failed"]) == (9, 8, 1)
        assert len(result["items"]) == 3 and sum(item["sent"] for item in result["series"]) == 8
        assert len(result["series"]) == 7 and result["series"][0]["sent"] == 0
        exported = analytics_router.export_analytics(days=7, session=session, user_id="owner").body.decode()
        assert "'=1+1" in exported and "test_sent" not in exported

    def sessions():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_session] = sessions
    app.dependency_overrides[get_current_user_id] = lambda: "owner"
    try:
        response = TestClient(app).get("/api/analytics?days=7&page=2")
        assert response.status_code == 200 and response.json()["sent"] == 8
        assert TestClient(app).get("/api/analytics?days=90").status_code == 422
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_current_user_id, None)
        engine.dispose()


def test_ui_migrations_preserve_existing_data_and_leave_unknown_dates_unknown():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE campaigns (id INTEGER, user_id TEXT, name TEXT)"))
        connection.execute(text("CREATE TABLE user_settings (user_id TEXT, timezone TEXT)"))
        connection.execute(text("CREATE TABLE templates (id INTEGER, title TEXT, body TEXT)"))
        connection.execute(text("INSERT INTO campaigns VALUES (1, 'owner', 'Keep me'), (2, 'other', 'Keep me too')"))
        connection.execute(text("INSERT INTO user_settings VALUES ('owner', 'Africa/Casablanca')"))
        connection.execute(text("INSERT INTO templates VALUES (1, 'Keep this', 'Body unchanged')"))
        for filename in ("0011_campaign_timezone.py", "0012_template_updated_at.py"):
            spec = importlib.util.spec_from_file_location("migration", Path(__file__).resolve().parents[1] / "alembic" / "versions" / filename)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
        assert connection.execute(text("SELECT name, timezone FROM campaigns ORDER BY id")).all() == [("Keep me", "Africa/Casablanca"), ("Keep me too", "UTC")]
        assert connection.execute(text("SELECT title, body, updated_at FROM templates")).one() == ("Keep this", "Body unchanged", None)
    engine.dispose()
