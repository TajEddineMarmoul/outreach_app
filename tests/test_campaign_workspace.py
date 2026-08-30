from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from api.routers.campaign_workspace import duplicate_campaign
from api.routers.campaign_delivery import clear_campaign_recipients, get_campaign_recipients
from src.platform.models import Base, Campaign, CampaignAttachment, CampaignRecipient, Contact, SendJob, SendLog, Sender, SenderGroup, AutopilotDaySchedule
from src.platform.services import ensure_user
from src.platform.time import utcnow


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'workspace.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE settings (key TEXT, user_id TEXT, value TEXT, PRIMARY KEY(key, user_id))"))
    with Session(engine) as session:
        ensure_user(session, "workspace-user")
        yield session
    engine.dispose()


def test_duplicate_is_an_independent_draft_without_delivery_work(session):
    source = Campaign(user_id="workspace-user", name="Fall hiring", status="autopilot", timezone="America/New_York",
                      subject_template="Hi {{first_name}}", body_template="Hello", scheduled_at=utcnow() + timedelta(hours=1),
                      send_settings={"mode": "autopilot", "delay_minutes": 5, "dry_run": True, "pause_reason": "daily_caps_reached", "draft_scheduled_at": "2026-01-01"})
    contact = Contact(user_id="workspace-user", email_normalized="lead@example.test", status="approved")
    session.add_all([source, contact])
    session.flush()
    session.add_all([
        CampaignRecipient(campaign_id=source.id, contact_id=contact.id, status="sent"),
        CampaignAttachment(campaign_id=source.id, filename="brief.txt", content_type="text/plain", size_bytes=3, sha256="abc", content=b"abc"),
        AutopilotDaySchedule(campaign_id=source.id, day_of_week="monday", daily_cap=10, start_time="09:00", end_time="16:30"),
    ])
    session.execute(text("INSERT INTO settings VALUES (:key, :user, :value)"), {"key": f"campaign_{source.id}_require_attachment", "user": "workspace-user", "value": '"true"'})
    session.commit()
    result = duplicate_campaign(source.id, session, "workspace-user")
    copied = session.get(Campaign, result["id"])
    assert copied.status == "draft" and copied.scheduled_at is None
    assert copied.name == "Fall hiring (copy)" and copied.timezone == source.timezone
    assert copied.subject_template == source.subject_template
    assert copied.send_settings == {"mode": "autopilot", "delay_minutes": 5, "dry_run": True}
    assert session.get(CampaignRecipient, (copied.id, contact.id)).status == "approved"
    assert session.get(CampaignRecipient, (source.id, contact.id)).status == "sent"
    attachment = session.scalar(select(CampaignAttachment).where(CampaignAttachment.campaign_id == copied.id))
    original_attachment = session.scalar(select(CampaignAttachment).where(CampaignAttachment.campaign_id == source.id))
    assert attachment.id != original_attachment.id and attachment.content == b"abc"
    assert copied.attachment_metadata["attachments"][0]["id"] == attachment.id
    assert session.scalar(select(AutopilotDaySchedule).where(AutopilotDaySchedule.campaign_id == copied.id)).start_time == "09:00"
    assert session.scalar(text("SELECT value FROM settings WHERE key = :key"), {"key": f"campaign_{copied.id}_require_attachment"}) == '"true"'
    assert session.scalar(select(func.count()).select_from(SendJob)) == 0
    assert source.status == "autopilot"
    session.delete(attachment)
    session.commit()
    assert session.get(CampaignAttachment, original_attachment.id).content == b"abc"


def test_duplicate_cannot_access_another_users_campaign(session):
    source = Campaign(user_id="workspace-user", name="Private")
    session.add(source)
    session.commit()
    with pytest.raises(HTTPException) as error:
        duplicate_campaign(source.id, session, "another-user")
    assert error.value.status_code == 404
    assert session.scalar(select(func.count()).select_from(Campaign)) == 1


def test_upcoming_recipients_filter_runs_before_pagination(session):
    campaign = Campaign(user_id="workspace-user", name="Long campaign")
    session.add(campaign)
    session.flush()
    for index, (recipient_status, contact_status) in enumerate([("sent", "sent"), ("failed", "approved"), ("approved", "approved"), ("queued", "approved"), ("approved", "rejected")]):
        contact = Contact(user_id="workspace-user", email_normalized=f"lead{index}@example.test", status=contact_status)
        session.add(contact)
        session.flush()
        session.add(CampaignRecipient(campaign_id=campaign.id, contact_id=contact.id, status=recipient_status))
    session.commit()
    result = get_campaign_recipients(campaign.id, search="", page=1, page_size=1, pending_only=True, session=session, user_id="workspace-user")
    assert result["total"] == 2
    assert result["items"][0]["email"] == "lead2@example.test"


def _audience_with_delivery(session, status="draft", job_status="queued"):
    campaign = Campaign(user_id="workspace-user", name="Keep this message", status=status,
                        subject_template="Hello", send_settings={"mode": "send_now", "dry_run": True,
                                                                 "recipient_validation": {"ready_recipient_count": 12}})
    other = Campaign(user_id="workspace-user", name="Other campaign")
    group = SenderGroup(user_id="workspace-user", name="Test senders")
    session.add_all([campaign, other, group])
    session.flush()
    sender = Sender(user_id="workspace-user", group_id=group.id, email="sender@example.test")
    session.add(sender)
    session.flush()
    for index in range(12):
        contact = Contact(user_id="workspace-user", email_normalized=f"person{index}@example.test", status="approved")
        session.add(contact)
        session.flush()
        session.add(CampaignRecipient(campaign_id=campaign.id, contact_id=contact.id))
    session.add_all([
        CampaignRecipient(campaign_id=other.id, contact_id=contact.id),
        SendJob(user_id="workspace-user", campaign_id=campaign.id, recipient_id=contact.id, sender_id=sender.id,
                status=job_status, batch_id="target", idempotency_key="target"),
        SendJob(user_id="workspace-user", campaign_id=other.id, recipient_id=contact.id, sender_id=sender.id,
                batch_id="other", idempotency_key="other"),
        SendLog(user_id="workspace-user", campaign_id=campaign.id, recipient_id=contact.id,
                recipient_email=contact.email_normalized, status="sent"),
        CampaignAttachment(campaign_id=campaign.id, filename="brief.txt", content_type="text/plain",
                           size_bytes=3, sha256="abc", content=b"abc"),
        AutopilotDaySchedule(campaign_id=campaign.id, day_of_week="monday", daily_cap=10,
                             start_time="09:00", end_time="16:30"),
    ])
    session.commit()
    return campaign, other


def test_clear_audience_removes_all_pages_but_keeps_contacts_history_and_configuration(session):
    campaign, other = _audience_with_delivery(session)
    assert clear_campaign_recipients(campaign.id, session, "workspace-user")["removed"] == 12
    assert session.scalar(select(func.count()).select_from(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign.id)) == 0
    assert session.scalar(select(func.count()).select_from(CampaignRecipient).where(CampaignRecipient.campaign_id == other.id)) == 1
    assert session.scalar(select(func.count()).select_from(SendJob).where(SendJob.campaign_id == campaign.id)) == 0
    assert session.scalar(select(func.count()).select_from(SendJob).where(SendJob.campaign_id == other.id)) == 1
    assert session.scalar(select(func.count()).select_from(Contact)) == 12
    assert session.scalar(select(func.count()).select_from(SendLog)) == 1
    assert session.scalar(select(CampaignAttachment).where(CampaignAttachment.campaign_id == campaign.id)).content == b"abc"
    assert session.scalar(select(AutopilotDaySchedule).where(AutopilotDaySchedule.campaign_id == campaign.id)).daily_cap == 10
    assert campaign.subject_template == "Hello" and campaign.status == "draft"
    assert campaign.send_settings == {"mode": "send_now", "dry_run": True}
    assert clear_campaign_recipients(campaign.id, session, "workspace-user")["removed"] == 0


@pytest.mark.parametrize("status", ["sending", "scheduled", "autopilot", "paused"])
def test_clear_audience_blocks_active_campaigns(session, status):
    campaign, _ = _audience_with_delivery(session, status=status)
    with pytest.raises(HTTPException) as error:
        clear_campaign_recipients(campaign.id, session, "workspace-user")
    assert error.value.status_code == 409
    assert session.scalar(select(func.count()).select_from(CampaignRecipient)) == 13


def test_clear_audience_waits_for_inflight_email_even_after_campaign_ends(session):
    campaign, _ = _audience_with_delivery(session, status="stopped", job_status="running")
    with pytest.raises(HTTPException) as error:
        clear_campaign_recipients(campaign.id, session, "workspace-user")
    assert error.value.status_code == 409
    assert session.scalar(select(func.count()).select_from(SendJob)) == 2


def test_clear_audience_cannot_access_another_users_campaign(session):
    campaign, _ = _audience_with_delivery(session)
    with pytest.raises(HTTPException) as error:
        clear_campaign_recipients(campaign.id, session, "another-user")
    assert error.value.status_code == 404
    assert session.scalar(select(func.count()).select_from(CampaignRecipient)) == 13
