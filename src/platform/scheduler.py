from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.platform.jobs import create_send_jobs_for_next_batch
from src.platform.models import AutopilotDaySchedule, Campaign, SendJob, UserSettings
from src.platform.time import utcnow


WEEKDAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _clock(value: str, fallback: time) -> time:
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError):
        return fallback


def _load_day_schedules(session: Session, campaign: Campaign) -> dict[str, AutopilotDaySchedule]:
    schedules = list(
        session.scalars(
            select(AutopilotDaySchedule).where(AutopilotDaySchedule.campaign_id == campaign.id)
        )
    )
    return {s.day_of_week: s for s in schedules}


def next_autopilot_run(
    session: Session,
    campaign: Campaign,
    *,
    now: datetime | None = None,
    force_next_day: bool = False,
) -> datetime:
    current = now or utcnow()
    settings = campaign.send_settings or {}
    user_settings = session.get(UserSettings, campaign.user_id)
    try:
        zone = ZoneInfo(user_settings.timezone if user_settings else "UTC")
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("UTC")
    local_now = current.astimezone(zone)

    schedules = _load_day_schedules(session, campaign)
    if schedules:
        allowed_days = set(schedules.keys())
    else:
        allowed_days = set(settings.get("days") or WEEKDAY_NAMES[:5])

    first_offset = 1 if force_next_day else 0
    for offset in range(first_offset, 9):
        candidate_date = local_now.date() + timedelta(days=offset)
        day_name = WEEKDAY_NAMES[candidate_date.weekday()]
        if day_name not in allowed_days:
            continue
        if schedules and day_name in schedules:
            s = schedules[day_name]
            start = _clock(s.start_time, time(9, 0))
            end = _clock(s.end_time, time(17, 0))
        else:
            start = _clock(str(settings.get("start_time", "09:00")), time(9, 0))
            end = _clock(str(settings.get("end_time", "17:00")), time(17, 0))
        start_at = datetime.combine(candidate_date, start, tzinfo=zone)
        end_at = datetime.combine(candidate_date, end, tzinfo=zone)
        if offset == 0 and start_at <= local_now <= end_at:
            return current
        if start_at > local_now:
            return start_at.astimezone(timezone.utc)
    return (local_now + timedelta(days=1)).astimezone(timezone.utc)


def enqueue_due_campaign_batches(session: Session, *, limit: int = 25) -> list[dict]:
    now = utcnow()
    campaigns = list(
        session.scalars(
            select(Campaign)
            .where(
                Campaign.status.in_(("sending", "scheduled", "autopilot")),
                Campaign.scheduled_at.is_not(None),
                Campaign.scheduled_at <= now,
            )
            .order_by(Campaign.scheduled_at, Campaign.id)
            .limit(limit)
        )
    )
    results: list[dict] = []
    for campaign in campaigns:
        active_jobs = list(
            session.scalars(
                select(SendJob).where(
                    SendJob.campaign_id == campaign.id,
                    SendJob.status.in_(("queued", "running", "retry")),
                )
            )
        )
        if active_jobs:
            campaign.scheduled_at = now + timedelta(seconds=30)
            results.append({"campaign_id": campaign.id, "created": 0, "reason": "Current batch is still active"})
            continue

        delay_minutes = int((campaign.send_settings or {}).get("delay_minutes", 5))
        result = create_send_jobs_for_next_batch(
            session,
            user_id=campaign.user_id,
            campaign_id=campaign.id,
            delay_minutes=delay_minutes,
            scheduled_for=now,
        )
        if result.get("exhausted"):
            campaign.status = "ended"
            campaign.scheduled_at = None
        elif result.get("reason_code") in ("daily_caps_reached", "campaign_daily_cap_reached"):
            if (campaign.send_settings or {}).get("mode") == "autopilot" or campaign.status == "autopilot":
                campaign.status = "autopilot"
                campaign.scheduled_at = next_autopilot_run(session, campaign, now=now, force_next_day=True)
            else:
                campaign.status = "paused"
                campaign.scheduled_at = None
                campaign.send_settings = {
                    **(campaign.send_settings or {}),
                    "pause_reason": "daily_caps_reached",
                }
        elif not result.get("job_ids"):
            if (campaign.send_settings or {}).get("mode") == "autopilot":
                campaign.status = "autopilot"
                campaign.scheduled_at = now + timedelta(minutes=15)
            else:
                campaign.status = "paused"
                campaign.scheduled_at = None
        results.append({"campaign_id": campaign.id, **result})
    session.commit()
    for result in results:
        result["queued"] = len(result.get("job_ids", []))
    return results
