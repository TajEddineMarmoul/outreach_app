from __future__ import annotations

import logging
import hmac
import os
from datetime import datetime, time, timezone

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.auth import get_current_user_id
from src.platform.db import get_session
from src.platform.jobs import create_send_jobs_for_next_batch
from src.platform.models import AutopilotDaySchedule, Campaign, CampaignRecipient, Contact, SendJob, SendLog, Sender
from src.platform.scheduler import WEEKDAY_NAMES, next_autopilot_run
from src.platform.services import campaign_sent_today, connected_senders, ensure_user, require_group, serialize_group, set_user_timezone, user_zone
from src.platform.time import utcnow
from src.platform.worker import recover_stale_jobs, run_worker_cycle


router = APIRouter(tags=["campaign-delivery"])


@router.post("/internal/worker/tick", tags=["worker"])
def worker_tick(x_worker_token: str | None = Header(default=None)):
    expected = os.getenv("WORKER_TICK_TOKEN")
    if not expected or not x_worker_token or not hmac.compare_digest(x_worker_token, expected):
        raise HTTPException(status_code=401, detail="Invalid worker token")
    recovered = recover_stale_jobs(stale_after_minutes=10)
    processed = run_worker_cycle(max_jobs=25)
    return {"status": "ok", "recovered": recovered, "processed": processed}


class DeliveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timezone: str | None = Field(default=None, min_length=1, max_length=80)


class CampaignSenderGroupSelect(DeliveryRequest):
    sender_group_id: int


class SendNowRequest(DeliveryRequest):
    delay_minutes: int = Field(default=5, ge=0, le=1440)
    dry_run: bool = False


class ScheduleRequest(DeliveryRequest):
    scheduled_at: datetime
    delay_minutes: int = Field(default=5, ge=0, le=1440)
    dry_run: bool = False


class DayScheduleEntry(DeliveryRequest):
    cap: int = Field(..., ge=1)
    start: str = Field(default="09:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(default="17:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")

    @model_validator(mode="after")
    def validate_window(self):
        if time.fromisoformat(self.start) >= time.fromisoformat(self.end):
            raise ValueError("start must be earlier than end")
        return self


class AutopilotRequest(DeliveryRequest):
    schedule: dict[str, DayScheduleEntry] = Field(..., min_length=1)
    delay_minutes: int = Field(default=5, ge=0, le=1440)
    scheduled_at: datetime | None = None
    dry_run: bool = False

    @model_validator(mode="after")
    def validate_days(self):
        unknown = sorted(set(self.schedule) - set(WEEKDAY_NAMES))
        if unknown:
            raise ValueError(f"unknown autopilot days: {', '.join(unknown)}")
        return self


class SendSettingsUpdate(DeliveryRequest):
    mode: str | None = Field(default=None, pattern="^(send_now|schedule|autopilot)$")
    delay_minutes: int | None = Field(default=None, ge=0, le=1440)
    dry_run: bool | None = None
    scheduled_at: datetime | None = None
    schedule: dict[str, DayScheduleEntry] | None = None

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.mode == "autopilot" and not self.schedule:
            raise ValueError("autopilot requires at least one enabled day")
        if self.schedule is not None:
            unknown = sorted(set(self.schedule) - set(WEEKDAY_NAMES))
            if unknown:
                raise ValueError(f"unknown autopilot days: {', '.join(unknown)}")
        return self


EDIT_LOCKED_STATUSES = {"sending", "scheduled", "autopilot", "paused"}


def apply_request_timezone(
    session: Session,
    user_id: str,
    timezone_name: str | None,
) -> None:
    if timezone_name is None:
        return
    try:
        set_user_timezone(session, user_id, timezone_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def require_campaign_editable(session: Session, campaign_id: int, user_id: str) -> Campaign:
    campaign = require_campaign(session, campaign_id, user_id)
    if campaign.status in EDIT_LOCKED_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Stop the campaign before editing its composer, send options, or recipients",
        )
    return campaign


def require_campaign(session: Session, campaign_id: int, user_id: str) -> Campaign:
    campaign = session.scalar(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id)
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


def queued_job_ids(session: Session, campaign_id: int, user_id: str) -> list[int]:
    return list(
        session.scalars(
            select(SendJob.id)
            .where(
                SendJob.campaign_id == campaign_id,
                SendJob.user_id == user_id,
                SendJob.status.in_(("queued", "retry")),
            )
            .order_by(SendJob.id)
        )
    )


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
    campaign = session.scalar(select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id))
    if campaign:
        require_campaign_editable(session, campaign_id, user_id)
    else:
        campaign = ensure_campaign_shell(session, campaign_id=campaign_id, user_id=user_id)
    campaign.selected_sender_group_id = group.id
    session.commit()
    return {"status": "success", "sender_group": serialize_group(session, group)}


@router.patch("/api/campaigns/{campaign_id}/send-settings")
def patch_send_settings(
    campaign_id: int,
    req: SendSettingsUpdate,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    campaign = require_campaign_editable(session, campaign_id, user_id)
    apply_request_timezone(session, user_id, req.timezone)
    settings = dict(campaign.send_settings or {})
    if req.mode is not None:
        settings["mode"] = req.mode
    if req.delay_minutes is not None:
        settings["delay_minutes"] = req.delay_minutes
    if req.dry_run is not None:
        settings["dry_run"] = req.dry_run
    if "scheduled_at" in req.model_fields_set:
        if req.scheduled_at is None:
            settings.pop("draft_scheduled_at", None)
        else:
            scheduled_at = req.scheduled_at
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
            settings["draft_scheduled_at"] = scheduled_at.astimezone(timezone.utc).isoformat()
    campaign.send_settings = settings
    if req.schedule is not None:
        session.execute(delete(AutopilotDaySchedule).where(AutopilotDaySchedule.campaign_id == campaign.id))
        for day_name, entry in req.schedule.items():
            session.add(
                AutopilotDaySchedule(
                    campaign_id=campaign.id,
                    day_of_week=day_name,
                    daily_cap=entry.cap,
                    start_time=entry.start,
                    end_time=entry.end,
                )
            )
    session.commit()
    return {"status": "success", "send_settings": campaign.send_settings}


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
    campaign = require_campaign_editable(session, campaign_id, user_id)
    apply_request_timezone(session, user_id, req.timezone)
    previous_status = campaign.status
    logger.info("campaign id=%s status=%s sender_group_id=%s", campaign.id, campaign.status, campaign.selected_sender_group_id)
    try:
        campaign.status = "sending"
        campaign.send_settings = {
            **(campaign.send_settings or {}),
            "mode": "send_now",
            "delay_minutes": req.delay_minutes,
            "dry_run": req.dry_run,
            "pause_reason": None,
        }
        existing_ids = queued_job_ids(session, campaign_id, user_id)
        logger.info("existing queued/retry jobs count=%s", len(existing_ids))
        if existing_ids:
            session.commit()
            return {"status": "queued", "queued": len(existing_ids), "mode": "resume"}

        logger.info("creating new send jobs batch")
        result = create_send_jobs_for_next_batch(
            session,
            user_id=user_id,
            campaign_id=campaign_id,
            delay_minutes=req.delay_minutes,
        )
        logger.info("create_send_jobs result: %s", result)
        if result.get("exhausted"):
            campaign.status = "ended"
            campaign.scheduled_at = None
        elif result.get("reason_code") == "daily_caps_reached":
            campaign.status = "paused"
            campaign.scheduled_at = None
            campaign.send_settings = {
                **(campaign.send_settings or {}),
                "pause_reason": "daily_caps_reached",
            }
        elif not result.get("job_ids"):
            campaign.status = previous_status
        session.commit()
        job_ids = result.get("job_ids", [])
        if job_ids:
            result["queued"] = len(job_ids)
        else:
            logger.warning("no jobs created, reason: %s", result.get("reason", "unknown"))
            raise HTTPException(
                status_code=409,
                detail=result.get("reason", "No email was queued"),
            )
    except (LookupError, ValueError) as exc:
        logger.error("send-now error: %s", exc)
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "queued" if result.get("queued") else campaign.status, **result}


@router.post("/api/campaigns/{campaign_id}/schedule")
def post_schedule(
    campaign_id: int,
    req: ScheduleRequest,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    campaign = require_campaign_editable(session, campaign_id, user_id)
    apply_request_timezone(session, user_id, req.timezone)
    if not campaign.selected_sender_group_id:
        raise HTTPException(status_code=400, detail="Campaign does not have a sender group selected")
    try:
        group = require_group(session, user_id, campaign.selected_sender_group_id)
    except LookupError:
        raise HTTPException(status_code=400, detail="Selected sender group no longer exists")
    if not connected_senders(group):
        raise HTTPException(status_code=409, detail="Selected sender group has no connected senders")
    approved_recipients = session.scalar(
        select(func.count())
        .select_from(CampaignRecipient)
        .join(Contact, Contact.id == CampaignRecipient.contact_id)
        .where(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.status == "approved",
            Contact.status.in_(("approved", "sent")),
        )
    ) or 0
    if approved_recipients == 0:
        raise HTTPException(status_code=409, detail="Campaign has no approved recipients")
    scheduled_at = req.scheduled_at
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    campaign.status = "scheduled"
    campaign.scheduled_at = scheduled_at.astimezone(timezone.utc)
    campaign.send_settings = {
        **(campaign.send_settings or {}),
        "mode": "schedule",
        "delay_minutes": req.delay_minutes,
        "dry_run": req.dry_run,
        "pause_reason": None,
    }
    session.commit()
    return {"status": "scheduled", "scheduled_at": campaign.scheduled_at.isoformat()}


@router.post("/api/campaigns/{campaign_id}/autopilot/start")
def post_autopilot_start(
    campaign_id: int,
    req: AutopilotRequest,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    campaign = require_campaign_editable(session, campaign_id, user_id)
    apply_request_timezone(session, user_id, req.timezone)
    if not campaign.selected_sender_group_id:
        raise HTTPException(status_code=400, detail="Campaign does not have a sender group selected")
    try:
        group = require_group(session, user_id, campaign.selected_sender_group_id)
    except LookupError:
        raise HTTPException(status_code=400, detail="Selected sender group no longer exists")
    if not connected_senders(group):
        raise HTTPException(status_code=409, detail="Selected sender group has no connected senders")
    approved_recipients = session.scalar(
        select(func.count())
        .select_from(CampaignRecipient)
        .join(Contact, Contact.id == CampaignRecipient.contact_id)
        .where(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.status == "approved",
            Contact.status.in_(("approved", "sent")),
        )
    ) or 0
    if approved_recipients == 0:
        raise HTTPException(status_code=409, detail="Campaign has no approved recipients")

    campaign.status = "autopilot"
    campaign.send_settings = {
        **(campaign.send_settings or {}),
        "mode": "autopilot",
        "delay_minutes": req.delay_minutes,
        "dry_run": req.dry_run,
        "pause_reason": None,
    }

    session.execute(
        delete(AutopilotDaySchedule).where(AutopilotDaySchedule.campaign_id == campaign.id)
    )
    for day_name, entry in req.schedule.items():
        session.add(
            AutopilotDaySchedule(
                campaign_id=campaign.id,
                day_of_week=day_name,
                daily_cap=entry.cap,
                start_time=entry.start,
                end_time=entry.end,
            )
        )
    scheduled_at = req.scheduled_at
    if scheduled_at is not None:
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
        campaign.scheduled_at = scheduled_at.astimezone(timezone.utc)
    else:
        campaign.scheduled_at = next_autopilot_run(session, campaign, now=utcnow())
    session.commit()
    return {"status": "autopilot", "scheduled_at": campaign.scheduled_at.isoformat()}


@router.post("/api/campaigns/{campaign_id}/pause")
def post_pause(
    campaign_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    campaign = require_campaign(session, campaign_id, user_id)
    if campaign.status == "paused":
        return {"status": "paused"}
    if campaign.status not in {"sending", "scheduled", "autopilot"}:
        raise HTTPException(status_code=409, detail=f"Cannot pause a campaign that is {campaign.status}")
    campaign.status = "paused"
    session.commit()
    return {"status": "paused"}


@router.post("/api/campaigns/{campaign_id}/resume")
def post_resume(
    campaign_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    campaign = require_campaign(session, campaign_id, user_id)
    if campaign.status != "paused":
        raise HTTPException(status_code=409, detail=f"Cannot resume a campaign that is {campaign.status}")
    mode = (campaign.send_settings or {}).get("mode", "send_now")
    job_ids = queued_job_ids(session, campaign_id, user_id)
    campaign.status = "autopilot" if mode == "autopilot" else "sending"
    resume_at = campaign.scheduled_at
    if resume_at and resume_at.tzinfo is None:
        resume_at = resume_at.replace(tzinfo=timezone.utc)
    if not job_ids and mode == "schedule" and resume_at and resume_at > utcnow():
        campaign.status = "scheduled"
        session.commit()
        return {
            "status": "scheduled",
            "queued": 0,
            "scheduled_at": campaign.scheduled_at.isoformat(),
        }
    result: dict = {}
    if not job_ids:
        try:
            result = create_send_jobs_for_next_batch(
                session,
                user_id=user_id,
                campaign_id=campaign_id,
                delay_minutes=int((campaign.send_settings or {}).get("delay_minutes", 5)),
            )
        except (LookupError, ValueError) as exc:
            session.rollback()
            raise HTTPException(status_code=400, detail=str(exc))
        job_ids = result.get("job_ids", [])
        if result.get("exhausted"):
            campaign.status = "ended"
            campaign.scheduled_at = None
        elif result.get("reason_code") in ("daily_caps_reached", "campaign_daily_cap_reached"):
            if mode == "autopilot":
                campaign.status = "autopilot"
                campaign.scheduled_at = next_autopilot_run(session, campaign, now=utcnow(), force_next_day=True)
            else:
                campaign.status = "paused"
                campaign.scheduled_at = None
                campaign.send_settings = {
                    **(campaign.send_settings or {}),
                    "pause_reason": result.get("reason_code", "daily_caps_reached"),
                }
        elif result.get("reason_code") in ("autopilot_day_disabled", "autopilot_outside_window"):
            campaign.status = "autopilot"
            campaign.scheduled_at = next_autopilot_run(session, campaign, now=utcnow())
            campaign.send_settings = {
                **(campaign.send_settings or {}),
                "pause_reason": result["reason_code"],
            }
    if job_ids:
        campaign.send_settings = {
            **(campaign.send_settings or {}),
            "pause_reason": None,
        }
    session.commit()
    if not job_ids:
        if mode == "autopilot" and campaign.status == "autopilot":
            return {
                "status": "autopilot",
                "queued": 0,
                "reason": result.get("reason"),
                "scheduled_at": campaign.scheduled_at.isoformat() if campaign.scheduled_at else None,
            }
        raise HTTPException(
            status_code=409,
            detail=result.get("reason", "No email was queued"),
        )
    return {"status": campaign.status, "queued": len(job_ids)}


@router.post("/api/campaigns/{campaign_id}/stop")
def post_stop(
    campaign_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    campaign = require_campaign(session, campaign_id, user_id)
    if campaign.status == "stopped":
        return {"status": "stopped", "cancelled": 0, "in_flight": 0}
    if campaign.status not in {"sending", "scheduled", "autopilot", "paused"}:
        raise HTTPException(status_code=409, detail=f"Cannot stop a campaign that is {campaign.status}")
    cancellable_jobs = list(
        session.scalars(
            select(SendJob).where(
                SendJob.campaign_id == campaign_id,
                SendJob.status.in_(("queued", "retry")),
            )
        )
    )
    for job in cancellable_jobs:
        recipient = session.get(
            CampaignRecipient,
            {"campaign_id": campaign_id, "contact_id": job.recipient_id},
        )
        if recipient and recipient.status == "queued":
            recipient.status = "approved"
        # Remove unclaimed attempts so a later start can reuse the recipient's
        # idempotency key. Claimed work remains for the worker to finalize.
        session.delete(job)
    in_flight = session.scalar(
        select(func.count()).select_from(SendJob).where(
            SendJob.campaign_id == campaign_id,
            SendJob.status == "running",
        )
    ) or 0
    campaign.status = "stopped"
    campaign.scheduled_at = None
    session.commit()
    return {"status": "stopped", "cancelled": len(cancellable_jobs), "in_flight": in_flight}


@router.get("/api/campaigns/{campaign_id}/send-progress")
def get_campaign_send_progress(
    campaign_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    logger = logging.getLogger("outreach.send")
    campaign = require_campaign(session, campaign_id, user_id)
    total = session.scalar(
        select(func.count()).select_from(CampaignRecipient)
        .where(CampaignRecipient.campaign_id == campaign_id)
    ) or 0
    sent = session.scalar(
        select(func.count())
        .select_from(CampaignRecipient)
        .where(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.status == "sent",
        )
    ) or 0
    failed = session.scalar(
        select(func.count())
        .select_from(CampaignRecipient)
        .where(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.status == "failed",
        )
    ) or 0
    running_job = session.scalar(
        select(SendJob).where(SendJob.campaign_id == campaign_id, SendJob.status == "running").limit(1)
    )
    queued = session.scalar(
        select(func.count()).select_from(SendJob)
        .where(SendJob.campaign_id == campaign_id, SendJob.status.in_(("queued", "retry")))
    ) or 0
    current_recipient = None
    if running_job:
        contact = session.get(Contact, running_job.recipient_id)
        if contact:
            current_recipient = contact.email_normalized
    campaign_sender_counts = dict(
        session.execute(
            select(SendLog.sender_id, func.count(func.distinct(SendLog.recipient_id)).label("count"))
            .join(
                CampaignRecipient,
                (CampaignRecipient.campaign_id == SendLog.campaign_id)
                & (CampaignRecipient.contact_id == SendLog.recipient_id),
            )
            .where(
                SendLog.campaign_id == campaign_id,
                SendLog.user_id == user_id,
                SendLog.status.in_(("sent", "test_sent")),
                (CampaignRecipient.reset_at.is_(None) | (SendLog.sent_at >= CampaignRecipient.reset_at)),
            )
            .group_by(SendLog.sender_id)
        ).all()
    )
    sender_details = []
    if campaign.selected_sender_group_id:
        try:
            group = require_group(session, user_id, campaign.selected_sender_group_id)
            group_payload = serialize_group(session, group)
            for sender in group_payload["senders"]:
                daily_cap = sender["daily_cap"]
                remaining = sender["daily_cap_remaining"]
                warning_threshold = max(2, int(daily_cap * 0.2))
                sender_details.append(
                    {
                        "id": sender["id"],
                        "email": sender["email"],
                        "status": sender["status"],
                        "campaign_sent": campaign_sender_counts.get(sender["id"], 0),
                        "sent_today": sender["sent_today"],
                        "daily_cap": daily_cap,
                        "remaining_today": remaining,
                        "capacity_state": "exhausted" if remaining == 0 else "low" if remaining <= warning_threshold else "available",
                        "last_error": sender["last_error"],
                    }
                )
        except LookupError:
            pass
    is_running = running_job is not None
    has_pending_work = sent + failed < total
    worker_managed = campaign.status in {"sending", "scheduled", "autopilot"}
    is_waiting = worker_managed and has_pending_work and not is_running and queued == 0
    pause_reason = (campaign.send_settings or {}).get("pause_reason")
    day_schedules = list(
        session.scalars(
            select(AutopilotDaySchedule).where(AutopilotDaySchedule.campaign_id == campaign.id)
        )
    )
    today_schedule = next(
        (s for s in day_schedules if s.day_of_week == WEEKDAY_NAMES[utcnow().astimezone(user_zone(session, user_id)).weekday()]),
        None,
    )
    result = {
        "campaign_status": campaign.status,
        "timezone": user_zone(session, user_id).key,
        "total_recipients": total,
        "sent_count": sent,
        "failed_count": failed,
        "queued_count": queued,
        "is_active": worker_managed and has_pending_work,
        "is_sending": is_running,
        "is_waiting": is_waiting,
        "current_recipient": current_recipient,
        "next_batch_at": campaign.scheduled_at.isoformat() if campaign.scheduled_at else None,
        "delay_minutes": int((campaign.send_settings or {}).get("delay_minutes", 0)),
        "send_mode": (campaign.send_settings or {}).get("mode", "send_now"),
        "send_settings": dict(campaign.send_settings or {}),
        "pause_reason": pause_reason,
        "senders": sender_details,
        "autopilot_schedule": [
            {"day": s.day_of_week, "cap": s.daily_cap, "start": s.start_time, "end": s.end_time}
            for s in day_schedules
        ],
        "campaign_sent_today": campaign_sent_today(session, campaign.id) if today_schedule else None,
        "campaign_daily_cap": today_schedule.daily_cap if today_schedule else None,
        "dry_run": (campaign.send_settings or {}).get("dry_run", False),
    }
    logger.info("send-progress campaign=%s %s", campaign_id, {k: v for k, v in result.items() if k != "senders"})
    return result


@router.get("/api/campaigns/{campaign_id}/send-logs")
def get_campaign_send_logs(
    campaign_id: int,
    page: int = 1,
    page_size: int = 10,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    require_campaign(session, campaign_id, user_id)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)
    total = session.scalar(
        select(func.count()).select_from(SendLog)
        .where(SendLog.campaign_id == campaign_id, SendLog.user_id == user_id)
    ) or 0
    logs = list(
        session.scalars(
            select(SendLog)
            .where(SendLog.campaign_id == campaign_id, SendLog.user_id == user_id)
            .order_by(SendLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return {
        "items": [
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
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/api/campaigns/{campaign_id}/recipients")
def get_campaign_recipients(
    campaign_id: int,
    search: str = "",
    page: int = 1,
    page_size: int = 50,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    require_campaign(session, campaign_id, user_id)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)

    base = (
        select(CampaignRecipient, Contact)
        .join(Contact, CampaignRecipient.contact_id == Contact.id)
        .where(CampaignRecipient.campaign_id == campaign_id, Contact.user_id == user_id)
    )
    if search:
        base = base.where(Contact.email_normalized.ilike(f"%{search.strip()}%"))

    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        session.execute(
            base.order_by(CampaignRecipient.created_at, Contact.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )

    return {
        "items": [
            {
                "contact_id": cr.contact_id,
                "email": c.email_normalized,
                "custom_fields": c.custom_fields or {},
                "status": cr.status if c.status in {"approved", "sent"} else c.status,
                "source_type": c.source_type,
                "created_at": cr.created_at.isoformat() if cr.created_at else None,
            }
            for cr, c in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.patch("/api/campaigns/{campaign_id}/recipients/{contact_id}/reset")
def patch_recipient_reset(
    campaign_id: int,
    contact_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    require_campaign_editable(session, campaign_id, user_id)
    recipient = session.get(CampaignRecipient, {"campaign_id": campaign_id, "contact_id": contact_id})
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found in this campaign")
    session.execute(
        delete(SendJob).where(
            SendJob.campaign_id == campaign_id,
            SendJob.recipient_id == contact_id,
        )
    )
    recipient.status = "approved"
    contact = session.get(Contact, contact_id)
    if contact and contact.user_id == user_id and contact.status == "sent":
        contact.status = "approved"
    recipient.reset_at = utcnow()
    session.commit()
    return {"status": "success", "reset_at": recipient.reset_at.isoformat()}


@router.delete("/api/campaigns/{campaign_id}/recipients/{contact_id}")
def delete_campaign_recipient(
    campaign_id: int,
    contact_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    require_campaign_editable(session, campaign_id, user_id)
    recipient = session.get(CampaignRecipient, {"campaign_id": campaign_id, "contact_id": contact_id})
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found in this campaign")
    session.execute(
        delete(SendJob).where(
            SendJob.campaign_id == campaign_id,
            SendJob.recipient_id == contact_id,
        )
    )
    session.delete(recipient)
    session.commit()
    return {"status": "success"}
