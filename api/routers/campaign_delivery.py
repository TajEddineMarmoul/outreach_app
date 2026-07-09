from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user_id
from src.platform.db import get_session
from src.platform.jobs import create_send_jobs_for_next_batch, perform_send_job
from src.platform.models import Campaign, CampaignRecipient, Contact, SendJob, SendLog, Sender
from src.platform.services import ensure_user, require_group, serialize_group


router = APIRouter(tags=["campaign-delivery"])


class CampaignSenderGroupSelect(BaseModel):
    sender_group_id: int


class SendNowRequest(BaseModel):
    delay_minutes: int = Field(default=5, ge=0, le=1440)


class ScheduleRequest(BaseModel):
    scheduled_at: datetime
    delay_minutes: int = Field(default=5, ge=0, le=1440)


def ensure_campaign_shell(
    session: Session,
    *,
    campaign_id: int,
    user_id: str,
    name: str | None = None,
    subject_template: str = "",
    body_template: str = "",
    fallback_body_template: str = "",
) -> Campaign:
    ensure_user(session, user_id)
    campaign = session.scalar(select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id))
    if campaign:
        return campaign
    campaign = Campaign(
        id=campaign_id,
        user_id=user_id,
        name=name or f"Campaign {campaign_id}",
        subject_template=subject_template,
        body_template=body_template,
        fallback_body_template=fallback_body_template,
        status="draft",
    )
    session.add(campaign)
    session.flush()
    return campaign


@router.patch("/api/campaigns/{campaign_id}/sender-group")
def patch_campaign_sender_group(
    campaign_id: int,
    req: CampaignSenderGroupSelect,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    try:
        group = require_group(session, user_id, req.sender_group_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Sender group not found")
    campaign = ensure_campaign_shell(session, campaign_id=campaign_id, user_id=user_id)
    campaign.selected_sender_group_id = group.id
    session.commit()
    return {"status": "success", "sender_group": serialize_group(session, group)}


@router.get("/api/campaigns/{campaign_id}/sender-group")
def get_campaign_sender_group(
    campaign_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    campaign = session.scalar(select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id))
    if not campaign or not campaign.selected_sender_group_id:
        return {"sender_group": None}
    try:
        group = require_group(session, user_id, campaign.selected_sender_group_id)
    except LookupError:
        return {"sender_group": None}
    return {"sender_group": serialize_group(session, group)}


@router.post("/api/campaigns/{campaign_id}/send-now")
def post_send_now(
    campaign_id: int,
    req: SendNowRequest = SendNowRequest(),
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    logger = logging.getLogger("outreach.send")
    logger.info("send-now start campaign=%s user=%s", campaign_id, user_id)
    campaign = ensure_campaign_shell(session, campaign_id=campaign_id, user_id=user_id)
    logger.info("campaign id=%s status=%s sender_group_id=%s", campaign.id, campaign.status, campaign.selected_sender_group_id)
    if campaign.status in {"draft", "stopped", "ended"}:
        campaign.status = "sending"
        session.commit()
        logger.info("set campaign status to sending")
    try:
        existing = list(session.scalars(
            select(SendJob).where(
                SendJob.campaign_id == campaign_id,
                SendJob.status.in_(["queued", "retry"]),
            ).order_by(SendJob.id)
        ))
        logger.info("existing queued/retry jobs count=%s", len(existing))
        if existing:
            logger.info("resuming %s existing jobs", len(existing))
            session.commit()
            import threading
            def _run():
                for job in existing:
                    logger.info("processing existing job %s", job.id)
                    perform_send_job(job.id)
            threading.Thread(target=_run, daemon=True).start()
            return {"status": "queued", "queued": len(existing), "mode": "resume"}
        logger.info("creating new send jobs batch")
        result = create_send_jobs_for_next_batch(
            session,
            user_id=user_id,
            campaign_id=campaign_id,
            delay_minutes=req.delay_minutes,
        )
        logger.info("create_send_jobs result: %s", result)
        session.commit()
        job_ids = result.get("job_ids", [])
        if job_ids:
            logger.info("spawning thread for %s jobs", len(job_ids))
            import threading
            def _run():
                for jid in job_ids:
                    logger.info("processing new job %s", jid)
                    perform_send_job(jid)
            threading.Thread(target=_run, daemon=True).start()
            result["queued"] = len(job_ids)
        else:
            logger.warning("no jobs created, reason: %s", result.get("reason", "unknown"))
    except (LookupError, ValueError) as exc:
        logger.error("send-now error: %s", exc)
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "queued", **result}


@router.get("/api/campaigns/{campaign_id}/send-progress")
def get_campaign_send_progress(
    campaign_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    logger = logging.getLogger("outreach.send")
    total = session.scalar(
        select(func.count()).select_from(CampaignRecipient)
        .where(CampaignRecipient.campaign_id == campaign_id)
    ) or 0
    sent = session.scalar(
        select(func.count()).select_from(SendLog)
        .where(SendLog.campaign_id == campaign_id, SendLog.user_id == user_id, SendLog.status.in_(["sent", "test_sent"]))
    ) or 0
    failed = session.scalar(
        select(func.count()).select_from(SendLog)
        .where(SendLog.campaign_id == campaign_id, SendLog.user_id == user_id, SendLog.status == "failed")
    ) or 0
    running_job = session.scalar(
        select(SendJob).where(SendJob.campaign_id == campaign_id, SendJob.status == "running").limit(1)
    )
    queued = session.scalar(
        select(func.count()).select_from(SendJob)
        .where(SendJob.campaign_id == campaign_id, SendJob.status == "queued")
    ) or 0
    current_recipient = None
    if running_job:
        contact = session.get(Contact, running_job.recipient_id)
        if contact:
            current_recipient = contact.email_normalized
    sender_breakdown = list(
        session.execute(
            select(SendLog.sender_email, func.count().label("count"))
            .where(SendLog.campaign_id == campaign_id, SendLog.user_id == user_id)
            .group_by(SendLog.sender_email)
        )
    )
    result = {
        "total_recipients": total,
        "sent_count": sent,
        "failed_count": failed,
        "queued_count": queued,
        "is_active": (queued > 0) or (running_job is not None),
        "current_recipient": current_recipient,
        "senders": [{"email": row[0], "count": row[1]} for row in sender_breakdown],
    }
    logger.info("send-progress campaign=%s %s", campaign_id, {k: v for k, v in result.items() if k != "senders"})
    return result


@router.get("/api/campaigns/{campaign_id}/send-logs")
def get_campaign_send_logs(
    campaign_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    logs = list(
        session.scalars(
            select(SendLog)
            .where(SendLog.campaign_id == campaign_id, SendLog.user_id == user_id)
            .order_by(SendLog.created_at.desc())
            .limit(100)
        )
    )
    return [
        {
            "id": log.id,
            "recipient_email": log.recipient_email,
            "sender_email": log.sender_email,
            "subject": log.subject,
            "status": log.status,
            "error_message": log.error_message,
            "sent_at": log.sent_at.isoformat() if log.sent_at else None,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
