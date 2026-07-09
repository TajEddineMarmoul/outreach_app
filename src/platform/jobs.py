from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta

from jinja2 import Environment
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.gmail_sender import send_email
from src.platform.db import SessionLocal
from src.platform.gmail import gmail_service_for_sender
from src.platform.models import Campaign, CampaignRecipient, Contact, Sender, SendJob, SendLog
from src.platform.services import eligible_senders, require_group
from src.platform.time import utcnow


TEMPLATE_ENV = Environment(autoescape=False)


def _render(template: str, context: dict) -> str:
    return TEMPLATE_ENV.from_string(template or "").render(**context)


def _rq_queue():
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None
    from redis import Redis
    from rq import Queue

    return Queue("outreach-send", connection=Redis.from_url(redis_url))


def enqueue_rq_jobs(job_ids: list[int]) -> int:
    queue = _rq_queue()
    if queue is None:
        return 0
    for job_id in job_ids:
        queue.enqueue("src.platform.jobs.perform_send_job", job_id, job_timeout="10m")
    return len(job_ids)


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
    senders = eligible_senders(session, group)
    if not senders:
        return {"created": 0, "queued": 0, "reason": "No eligible connected senders in selected group"}

    recipients = list(
        session.scalars(
            select(CampaignRecipient)
            .where(CampaignRecipient.campaign_id == campaign_id)
            .order_by(CampaignRecipient.created_at, CampaignRecipient.contact_id)
            .limit(len(senders))
        )
    )
    if not recipients:
        return {"created": 0, "queued": 0, "reason": "No approved recipients are ready"}

    scheduled = scheduled_for or utcnow()
    batch_id = secrets.token_urlsafe(16)
    created_ids: list[int] = []
    for recipient, sender in zip(recipients, senders):
        idempotency_key = f"campaign:{campaign_id}:recipient:{recipient.contact_id}"
        exists = session.scalar(select(SendJob.id).where(SendJob.idempotency_key == idempotency_key))
        if exists:
            continue
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
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            continue
        created_ids.append(job.id)

    if created_ids and campaign.status == "draft":
        campaign.status = "sending"
    if created_ids:
        campaign.scheduled_at = scheduled + timedelta(minutes=delay_minutes)

    return {
        "created": len(created_ids),
        "queued": 0,
        "job_ids": created_ids,
        "batch_id": batch_id,
        "next_batch_due_at": (scheduled + timedelta(minutes=delay_minutes)).isoformat(),
    }


def perform_send_job(job_id: int) -> dict:
    logger = logging.getLogger("outreach.send")
    logger.info("perform_send_job start job_id=%s", job_id)
    session = SessionLocal()
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
        if job.status not in {"queued", "retry"}:
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
            return {"status": "skipped"}
        if sender.status != "connected" or not sender.encrypted_oauth_credentials:
            logger.error("job %s sender not connected: status=%s has_creds=%s", job_id, sender.status, bool(sender.encrypted_oauth_credentials))
            raise RuntimeError("Sender is not connected.")

        job.status = "running"
        job.locked_at = utcnow()
        job.attempts += 1
        context = dict(contact.custom_fields or {})
        context.setdefault("email", contact.email_normalized)
        subject = _render(campaign.subject_template, context)
        body = _render(campaign.body_template or campaign.fallback_body_template, context)
        log = SendLog(
            user_id=job.user_id,
            campaign_id=job.campaign_id,
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

        result = send_email(
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
            sender = session.get(Sender, job.sender_id)
            if sender:
                sender.status = "error"
                sender.last_error = str(exc)
                sender.recent_error_at = utcnow()
            session.commit()
        return {"status": "failed", "job_id": job_id, "error": str(exc)}
    finally:
        session.close()
