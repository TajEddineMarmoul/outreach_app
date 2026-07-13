from __future__ import annotations

import logging
import json
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jinja2 import Environment
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.gmail_sender import fake_send_email, send_email
from src.platform.db import SessionLocal
from src.platform.gmail import gmail_service_for_sender
from src.platform.models import AutopilotDaySchedule, Campaign, CampaignRecipient, Contact, Sender, SendJob, SendLog, UserSettings

WEEKDAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
from src.platform.services import (
    campaign_sent_today,
    connected_senders,
    eligible_senders,
    require_group,
    sender_sent_count_today,
)
from src.platform.time import utcnow


TEMPLATE_ENV = Environment(autoescape=False)


def _render(template: str, context: dict) -> str:
    return TEMPLATE_ENV.from_string(template or "").render(**context)


def _schedule_after_finished_batch(session: Session, job: SendJob, finished_at: datetime) -> None:
    session.flush()
    active_in_batch = session.scalar(
        select(func.count())
        .select_from(SendJob)
        .where(
            SendJob.batch_id == job.batch_id,
            SendJob.status.in_(("queued", "running", "retry")),
        )
    ) or 0
    if active_in_batch:
        return
    campaign = session.get(Campaign, job.campaign_id)
    if not campaign or campaign.status in {"paused", "stopped", "ended"}:
        return
    delay_minutes = int((campaign.send_settings or {}).get("delay_minutes", 5))
    campaign.scheduled_at = finished_at + timedelta(minutes=delay_minutes)


def create_send_jobs_for_next_batch(
    session: Session,
    *,
    user_id: str,
    campaign_id: int,
    delay_minutes: int = 5,
    scheduled_for: datetime | None = None,
) -> dict:
    campaign = session.scalar(select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id))
    if not campaign:
        raise LookupError("Campaign not found")
    if campaign.status in {"paused", "stopped", "ended"}:
        return {"created": 0, "queued": 0, "reason": f"Campaign is {campaign.status}"}
    if not campaign.selected_sender_group_id:
        raise ValueError("Campaign does not have a sender group selected")

    group = require_group(session, user_id, campaign.selected_sender_group_id)
    connected = connected_senders(group)
    senders = eligible_senders(session, group)
    if not senders:
        if not connected:
            reason_code = "no_connected_senders"
            reason = "No eligible connected senders in selected group"
        elif all(sender_sent_count_today(session, sender.id) >= sender.daily_cap for sender in connected):
            reason_code = "daily_caps_reached"
            reason = "All senders in the selected group reached their daily cap"
        else:
            reason_code = "senders_temporarily_unavailable"
            reason = "Connected senders are temporarily unavailable"
        return {"created": 0, "queued": 0, "reason_code": reason_code, "reason": reason}

    max_to_send = len(senders)
    is_autopilot = (campaign.send_settings or {}).get("mode") == "autopilot"
    if is_autopilot:
        user_settings = session.get(UserSettings, campaign.user_id)
        try:
            zone = ZoneInfo(user_settings.timezone if user_settings else "UTC")
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        today_name = WEEKDAY_NAMES[utcnow().astimezone(zone).weekday()]
        day_schedule = session.scalar(
            select(AutopilotDaySchedule).where(
                AutopilotDaySchedule.campaign_id == campaign.id,
                AutopilotDaySchedule.day_of_week == today_name,
            )
        )
        if day_schedule:
            sent_today = campaign_sent_today(session, campaign.id)
            remaining_campaign = day_schedule.daily_cap - sent_today
            if remaining_campaign <= 0:
                return {
                    "created": 0,
                    "queued": 0,
                    "reason_code": "campaign_daily_cap_reached",
                    "reason": "Campaign reached its daily sending limit",
                }
            max_to_send = min(max_to_send, remaining_campaign)

    session.execute(
        update(CampaignRecipient)
        .where(
            CampaignRecipient.campaign_id == campaign_id,
            or_(
                CampaignRecipient.status.is_(None),
                func.trim(CampaignRecipient.status) == "",
            ),
        )
        .values(status="approved")
    )
    existing_job = (
        select(SendJob.id)
        .where(
            SendJob.campaign_id == campaign_id,
            SendJob.recipient_id == CampaignRecipient.contact_id,
            SendJob.status.in_(("queued", "running", "retry", "sent")),
        )
        .exists()
    )
    recipients = list(
        session.scalars(
            select(CampaignRecipient)
            .join(Contact, Contact.id == CampaignRecipient.contact_id)
            .where(
                CampaignRecipient.campaign_id == campaign_id,
                Contact.user_id == user_id,
                Contact.status == "approved",
                CampaignRecipient.status == "approved",
                ~existing_job,
            )
            .order_by(CampaignRecipient.created_at, CampaignRecipient.contact_id)
            .limit(max_to_send)
        )
    )
    if not recipients:
        return {
            "created": 0,
            "queued": 0,
            "exhausted": True,
            "reason": "No unsent approved recipients are ready",
        }

    scheduled = scheduled_for or utcnow()
    batch_id = secrets.token_urlsafe(16)
    created_ids: list[int] = []
    for recipient, sender in zip(recipients, senders):
        idempotency_key = f"campaign:{campaign_id}:recipient:{recipient.contact_id}"
        try:
            with session.begin_nested():
                job = SendJob(
                    user_id=user_id,
                    campaign_id=campaign_id,
                    recipient_id=recipient.contact_id,
                    sender_id=sender.id,
                    status="queued",
                    scheduled_for=scheduled,
                    batch_id=batch_id,
                    idempotency_key=idempotency_key,
                )
                session.add(job)
                recipient.status = "queued"
                session.flush()
                job_id = job.id
        except IntegrityError:
            continue
        created_ids.append(job_id)

    if not created_ids:
        return {
            "created": 0,
            "queued": 0,
            "exhausted": False,
            "reason": "Recipients were queued by another request",
        }

    if created_ids and campaign.status in {"draft", "scheduled"}:
        campaign.status = "sending"
    if created_ids:
        campaign.scheduled_at = scheduled + timedelta(minutes=delay_minutes)

    return {
        "created": len(created_ids),
        "queued": 0,
        "job_ids": created_ids,
        "batch_id": batch_id,
        "exhausted": False,
        "next_batch_due_at": (scheduled + timedelta(minutes=delay_minutes)).isoformat(),
    }


def perform_send_job(job_id: int, *, claimed: bool = False) -> dict:
    logger = logging.getLogger("outreach.send")
    logger.info("perform_send_job start job_id=%s", job_id)
    session = SessionLocal()
    attempt_log_id: int | None = None
    try:
        job = session.get(SendJob, job_id)
        if not job:
            logger.warning("job %s not found", job_id)
        else:
            logger.info("job %s status=%s campaign=%s sender=%s recipient=%s", job_id, job.status, job.campaign_id, job.sender_id, job.recipient_id)
        if not job:
            return {"status": "missing"}
        if job.status == "sent":
            return {"status": "already_sent"}
        allowed_statuses = {"queued", "retry", "running"} if claimed else {"queued", "retry"}
        if job.status not in allowed_statuses:
            return {"status": job.status}

        campaign = session.get(Campaign, job.campaign_id)
        contact = session.get(Contact, job.recipient_id)
        sender = session.get(Sender, job.sender_id)
        recipient = session.get(CampaignRecipient, {"campaign_id": job.campaign_id, "contact_id": job.recipient_id})
        if not campaign or not contact or not sender or not recipient:
            msg = "Campaign, contact, sender, or campaign recipient no longer exists."
            logger.error("job %s missing entities: campaign=%s contact=%s sender=%s recipient=%s", job_id, campaign is not None, contact is not None, sender is not None, recipient is not None)
            job.status = "failed"
            job.error_message = msg
            session.commit()
            return {"status": "failed", "error": msg}
        logger.info("job %s campaign_status=%s recipient_status=%s sender_status=%s has_creds=%s", job_id, campaign.status, recipient.status, sender.status, bool(sender.encrypted_oauth_credentials))
        if campaign.status in {"paused", "stopped", "ended"} or recipient.status not in {"queued", "approved"}:
            logger.info("job %s skipped: campaign=%s recipient=%s", job_id, campaign.status, recipient.status)
            if campaign.status == "paused":
                job.status = "queued"
                job.locked_at = None
                session.commit()
                return {"status": "paused"}
            job.status = "cancelled"
            job.locked_at = None
            session.commit()
            return {"status": "cancelled"}
        if sender.status != "connected" or not sender.encrypted_oauth_credentials:
            logger.error("job %s sender not connected: status=%s has_creds=%s", job_id, sender.status, bool(sender.encrypted_oauth_credentials))
            raise RuntimeError("Sender is not connected.")

        if not claimed:
            job.status = "running"
            job.locked_at = utcnow()
        job.attempts += 1
        custom_fields = contact.custom_fields or {}
        if isinstance(custom_fields, str):
            custom_fields = json.loads(custom_fields)
        context = dict(custom_fields)
        context.setdefault("email", contact.email_normalized)
        subject = _render(campaign.subject_template, context)
        body = _render(campaign.body_template or campaign.fallback_body_template, context)
        log = SendLog(
            user_id=job.user_id,
            campaign_id=job.campaign_id,
            contact_id=job.recipient_id,
            recipient_id=job.recipient_id,
            sender_id=job.sender_id,
            recipient_email=contact.email_normalized,
            sender_email=sender.email,
            subject=subject,
            body_snapshot=body,
            status="attempting",
        )
        session.add(log)
        session.flush()
        attempt_log_id = log.id
        session.commit()

        dry_run = (campaign.send_settings or {}).get("dry_run", False)
        send_fn = fake_send_email if dry_run else send_email
        result = send_fn(
            sender=sender.email,
            recipient=contact.email_normalized,
            subject=subject,
            body=body,
            attachment_path=(campaign.attachment_metadata or {}).get("path"),
            service=gmail_service_for_sender(session, sender),
        )
        now = utcnow()
        log.status = "sent"
        log.sent_at = now
        log.gmail_message_id = result.message_id
        log.gmail_thread_id = result.thread_id
        job.status = "sent"
        recipient.status = "sent"
        contact.status = "sent"
        sender.status = "connected"
        sender.last_error = None
        sender.recent_error_at = None
        _schedule_after_finished_batch(session, job, now)
        session.commit()
        logger.info("perform_send_job success job_id=%s gmail_id=%s", job_id, result.message_id)
        return {"status": "sent", "job_id": job_id}
    except Exception as exc:
        logger.error("perform_send_job failed job_id=%s error=%s", job_id, exc)
        session.rollback()
        job = session.get(SendJob, job_id)
        if job:
            job.status = "retry" if job.attempts < job.max_attempts else "failed"
            job.error_message = str(exc)
            if attempt_log_id:
                attempt_log = session.get(SendLog, attempt_log_id)
                if attempt_log:
                    attempt_log.status = "failed"
                    attempt_log.error_message = str(exc)
            sender = session.get(Sender, job.sender_id)
            if sender:
                sender.last_error = str(exc)
                sender.recent_error_at = utcnow()
            _schedule_after_finished_batch(session, job, utcnow())
            session.commit()
        return {"status": "failed", "job_id": job_id, "error": str(exc)}
    finally:
        session.close()
