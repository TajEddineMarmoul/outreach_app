from __future__ import annotations

import asyncio
from io import BytesIO

from fastapi import UploadFile
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers

from api.routers import campaigns
from src.platform.models import Base, Campaign, CampaignAttachment
from src.platform.services import ensure_user


USER_ID = "attachment-user"


def make_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'attachments.db'}", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    ensure_user(session, USER_ID)
    campaign = Campaign(user_id=USER_ID, name="Attachment test", status="draft")
    session.add(campaign)
    session.commit()
    return session, campaign.id


def test_upload_persists_multiple_attachments_and_metadata(tmp_path, monkeypatch):
    session, campaign_id = make_session(tmp_path)
    monkeypatch.setattr(campaigns, "require_editable_campaign", lambda *_args: {"id": campaign_id})
    uploads = [
        UploadFile(
            filename="resume.pdf",
            file=BytesIO(b"%PDF-1.4 durable content"),
            headers=Headers({"content-type": "application/pdf"}),
        ),
        UploadFile(
            filename="portfolio.pdf",
            file=BytesIO(b"%PDF-1.4 portfolio content"),
            headers=Headers({"content-type": "application/pdf"}),
        ),
    ]

    result = asyncio.run(
        campaigns.post_attachments(
            campaign_id=campaign_id,
            files=uploads,
            conn=object(),
            platform_session=session,
            user_id=USER_ID,
        )
    )

    stored = session.scalars(
        select(CampaignAttachment)
        .where(CampaignAttachment.campaign_id == campaign_id)
        .order_by(CampaignAttachment.id)
    ).all()
    campaign = session.get(Campaign, campaign_id)
    assert [item["filename"] for item in result["attachments"]] == ["resume.pdf", "portfolio.pdf"]
    assert [item.content for item in stored] == [
        b"%PDF-1.4 durable content",
        b"%PDF-1.4 portfolio content",
    ]
    assert campaign.attachment_metadata["count"] == 2
    assert [item["filename"] for item in campaign.attachment_metadata["attachments"]] == [
        "resume.pdf",
        "portfolio.pdf",
    ]
    assert campaign.attachment_path == ""
    session.close()


def test_delete_removes_only_selected_attachment(tmp_path, monkeypatch):
    session, campaign_id = make_session(tmp_path)
    monkeypatch.setattr(campaigns, "require_editable_campaign", lambda *_args: {"id": campaign_id})
    first = CampaignAttachment(
        campaign_id=campaign_id,
        filename="first.pdf",
        content_type="application/pdf",
        size_bytes=5,
        sha256="first",
        content=b"first",
    )
    second = CampaignAttachment(
        campaign_id=campaign_id,
        filename="second.pdf",
        content_type="application/pdf",
        size_bytes=6,
        sha256="second",
        content=b"second",
    )
    session.add_all([first, second])
    session.commit()

    result = campaigns.delete_attachment(
        campaign_id=campaign_id,
        attachment_id=first.id,
        conn=object(),
        platform_session=session,
        user_id=USER_ID,
    )

    remaining = session.scalars(
        select(CampaignAttachment).where(CampaignAttachment.campaign_id == campaign_id)
    ).all()
    campaign = session.get(Campaign, campaign_id)
    assert result == {"status": "success"}
    assert [attachment.filename for attachment in remaining] == ["second.pdf"]
    assert campaign.attachment_metadata["count"] == 1
    assert campaign.attachment_metadata["attachments"][0]["filename"] == "second.pdf"
    session.close()


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _PreviewConnection:
    def __init__(self, rows):
        self.rows = rows
        self.query_count = 0

    def execute(self, _sql, _params):
        self.query_count += 1
        return _Rows(self.rows)


def test_preview_renders_only_requested_recipient(tmp_path, monkeypatch):
    session, campaign_id = make_session(tmp_path)
    campaign_row = {
        "id": campaign_id,
        "user_id": USER_ID,
        "subject_template": "Hello {{ First_Name }}",
        "body_template": "Message for {{ Email }}",
        "fallback_body_template": "",
        "attachment_path": "",
        "attachment_metadata": {},
    }
    recipient = {
        "id": 7,
        "email": "lead@example.com",
        "first_name": "Lead",
        "last_name": "",
        "full_name": "Lead Person",
        "company_name": "",
        "company_website": "",
        "linkedin": "",
        "title": "",
        "industry": "",
        "keywords": "",
        "keyword_1": "",
        "keyword_2": "",
        "keyword_3": "",
        "country": "",
        "custom_fields": {"First_Name": "Sandy", "Email": "lead@example.com"},
    }
    conn = _PreviewConnection([recipient])
    monkeypatch.setattr(campaigns.db, "get_campaign", lambda *_args: campaign_row)
    monkeypatch.setattr(campaigns.db, "campaign_contact_count", lambda *_args: 1000)

    result = campaigns.get_campaign_preview(
        campaign_id=campaign_id,
        offset=500,
        limit=1,
        conn=conn,
        platform_session=session,
        user_id=USER_ID,
    )

    assert result["total"] == 1000
    assert len(result["items"]) == 1
    assert result["items"][0]["subject"] == "Hello Sandy"
    assert result["items"][0]["attachments"] == []
    assert conn.query_count == 1
    session.close()
