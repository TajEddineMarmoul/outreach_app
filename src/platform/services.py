from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.platform.models import (
    Campaign,
    AutopilotDaySchedule,
    Contact,
    OAuthState,
    Sender,
    SenderGroup,
    SendLog,
    SendJob,
    User,
    UserSettings,
)
from src.platform.time import utcnow


CONNECTED_SENDER_STATUSES = {"connected"}
WEEKDAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
SENDER_ERROR_COOLDOWN = timedelta(minutes=15)


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def user_zone(session: Session, user_id: str) -> ZoneInfo:
    settings = session.get(UserSettings, user_id)
    try:
        return ZoneInfo(settings.timezone if settings else "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def validate_timezone_name(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Unknown IANA timezone") from exc
    return value


def local_day_bounds(session: Session, user_id: str, *, now: datetime | None = None) -> tuple[datetime, datetime]:
    zone = user_zone(session, user_id)
    local_midnight = _aware_utc(now or utcnow()).astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(timezone.utc), (local_midnight + timedelta(days=1)).astimezone(timezone.utc)


def _clock(value: str, fallback: time) -> time:
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError):
        return fallback


def _day_schedules(session: Session, campaign_id: int) -> dict[str, AutopilotDaySchedule]:
    schedules = session.scalars(
        select(AutopilotDaySchedule).where(AutopilotDaySchedule.campaign_id == campaign_id)
    )
    return {schedule.day_of_week: schedule for schedule in schedules}


def next_autopilot_run(
    session: Session,
    campaign: Campaign,
    *,
    now: datetime | None = None,
    force_next_day: bool = False,
) -> datetime:
    current = _aware_utc(now or utcnow())
    zone = user_zone(session, campaign.user_id)
    local_now = current.astimezone(zone)
    schedules = _day_schedules(session, campaign.id)
    settings = campaign.send_settings or {}
    allowed_days = set(schedules) if schedules else set(settings.get("days") or WEEKDAY_NAMES[:5])
    first_offset = 1 if force_next_day else 0
    for offset in range(first_offset, 9):
        candidate_date = local_now.date() + timedelta(days=offset)
        day_name = WEEKDAY_NAMES[candidate_date.weekday()]
        if day_name not in allowed_days:
            continue
        schedule = schedules.get(day_name)
        start = _clock(schedule.start_time if schedule else str(settings.get("start_time", "09:00")), time(9, 0))
        end = _clock(schedule.end_time if schedule else str(settings.get("end_time", "17:00")), time(17, 0))
        start_at = datetime.combine(candidate_date, start, tzinfo=zone)
        end_at = datetime.combine(candidate_date, end, tzinfo=zone)
        if offset == 0 and start_at <= local_now <= end_at:
            return current
        if start_at > local_now:
            return start_at.astimezone(timezone.utc)
    return (local_now + timedelta(days=1)).astimezone(timezone.utc)


def autopilot_window_state(session: Session, campaign: Campaign, *, now: datetime | None = None) -> dict:
    current = _aware_utc(now or utcnow())
    zone = user_zone(session, campaign.user_id)
    local_now = current.astimezone(zone)
    schedules = _day_schedules(session, campaign.id)
    settings = campaign.send_settings or {}
    day_name = WEEKDAY_NAMES[local_now.weekday()]
    allowed_days = set(schedules) if schedules else set(settings.get("days") or WEEKDAY_NAMES[:5])
    if day_name not in allowed_days:
        return {
            "allowed": False,
            "reason_code": "autopilot_day_disabled",
            "reason": "Autopilot is disabled today",
            "next_at": next_autopilot_run(session, campaign, now=current),
            "schedule": None,
        }
    schedule = schedules.get(day_name)
    start = _clock(schedule.start_time if schedule else str(settings.get("start_time", "09:00")), time(9, 0))
    end = _clock(schedule.end_time if schedule else str(settings.get("end_time", "17:00")), time(17, 0))
    start_at = datetime.combine(local_now.date(), start, tzinfo=zone)
    end_at = datetime.combine(local_now.date(), end, tzinfo=zone)
    if local_now < start_at or local_now > end_at:
        return {
            "allowed": False,
            "reason_code": "autopilot_outside_window",
            "reason": "Autopilot is outside today's sending window",
            "next_at": next_autopilot_run(session, campaign, now=current),
            "schedule": schedule,
        }
    return {"allowed": True, "reason_code": None, "reason": None, "next_at": current, "schedule": schedule}


def ensure_user(session: Session, user_id: str, email: str | None = None) -> User:
    user = session.get(User, user_id)
    if user:
        if email and user.email != email:
            user.email = email
        if session.get(UserSettings, user_id) is None:
            session.add(UserSettings(user_id=user_id))
            session.flush()
        return user
    user = User(id=user_id, email=email)
    session.add(user)
    session.add(UserSettings(user_id=user_id))
    session.flush()
    return user


def set_user_timezone(session: Session, user_id: str, timezone_name: str) -> bool:
    validate_timezone_name(timezone_name)
    ensure_user(session, user_id)
    settings = session.get(UserSettings, user_id)
    changed = settings.timezone != timezone_name
    settings.timezone = timezone_name
    session.flush()
    return changed


def require_group(session: Session, user_id: str, group_id: int) -> SenderGroup:
    group = session.scalar(
        select(SenderGroup)
        .options(selectinload(SenderGroup.senders))
        .where(SenderGroup.id == group_id, SenderGroup.user_id == user_id)
    )
    if not group:
        raise LookupError("Sender group not found")
    return group


def connected_senders(group: SenderGroup) -> list[Sender]:
    return sorted(
        [sender for sender in group.senders if sender.status == "connected" and sender.encrypted_oauth_credentials],
        key=lambda sender: sender.id,
    )


def sender_sent_count_today(
    session: Session,
    sender_id: int,
    *,
    now: datetime | None = None,
) -> int:
    sender = session.get(Sender, sender_id)
    if not sender:
        return 0
    start, end = local_day_bounds(session, sender.user_id, now=now)
    return int(
        session.scalar(
            select(func.count())
            .select_from(SendLog)
            .where(
                SendLog.sender_id == sender_id,
                SendLog.status == "sent",
                SendLog.sent_at >= start,
                SendLog.sent_at < end,
            )
        )
        or 0
    )


def campaign_sent_today(
    session: Session,
    campaign_id: int,
    *,
    now: datetime | None = None,
) -> int:
    campaign = session.get(Campaign, campaign_id)
    if not campaign:
        return 0
    start, end = local_day_bounds(session, campaign.user_id, now=now)
    return int(
        session.scalar(
            select(func.count())
            .select_from(SendLog)
            .where(
                SendLog.campaign_id == campaign_id,
                SendLog.status.in_(("sent", "test_sent")),
                SendLog.sent_at >= start,
                SendLog.sent_at < end,
            )
        )
        or 0
    )


def campaign_reserved_today(
    session: Session,
    campaign: Campaign,
    *,
    now: datetime | None = None,
) -> int:
    """Count queued work already reserved against today's campaign cap."""
    start, end = local_day_bounds(session, campaign.user_id, now=now)
    return int(
        session.scalar(
            select(func.count())
            .select_from(SendJob)
            .where(
                SendJob.campaign_id == campaign.id,
                SendJob.status.in_(("queued", "running", "retry")),
                SendJob.scheduled_for >= start,
                SendJob.scheduled_for < end,
            )
        )
        or 0
    )


def sender_reserved_today(
    session: Session,
    sender: Sender,
    *,
    now: datetime | None = None,
) -> int:
    """Count active jobs holding one of the sender's slots for the local day."""
    start, end = local_day_bounds(session, sender.user_id, now=now)
    return int(
        session.scalar(
            select(func.count())
            .select_from(SendJob)
            .where(
                SendJob.sender_id == sender.id,
                SendJob.status.in_(("queued", "running", "retry")),
                SendJob.scheduled_for >= start,
                SendJob.scheduled_for < end,
            )
        )
        or 0
    )


def delivery_policy_state(
    session: Session,
    campaign: Campaign,
    sender: Sender,
    *,
    now: datetime | None = None,
) -> dict:
    """Evaluate mutable send constraints immediately before external delivery."""
    current = _aware_utc(now or utcnow())
    if (campaign.send_settings or {}).get("mode") == "autopilot":
        window = autopilot_window_state(session, campaign, now=current)
        if not window["allowed"]:
            return window

        schedule = window["schedule"]
        if schedule:
            campaign_usage = campaign_sent_today(session, campaign.id, now=current)
            campaign_reservations = campaign_reserved_today(session, campaign, now=current)
            if campaign_usage + campaign_reservations > schedule.daily_cap:
                return {
                    "allowed": False,
                    "reason_code": "campaign_daily_cap_reached",
                    "reason": "Campaign reached its daily sending limit",
                    "next_at": next_autopilot_run(
                        session,
                        campaign,
                        now=current,
                        force_next_day=True,
                    ),
                }

    sent_by_sender = sender_sent_count_today(session, sender.id, now=current)
    sender_reservations = sender_reserved_today(session, sender, now=current)
    if sent_by_sender + sender_reservations > sender.daily_cap:
        return {
            "allowed": False,
            "reason_code": "sender_daily_cap_reached",
            "reason": f"{sender.email} reached its daily sending limit",
            "next_at": None,
        }

    if sender.recent_error_at:
        cooldown_ends_at = _aware_utc(sender.recent_error_at) + SENDER_ERROR_COOLDOWN
        if current < cooldown_ends_at:
            return {
                "allowed": False,
                "reason_code": "sender_cooldown",
                "reason": f"{sender.email} is cooling down after a delivery error",
                "next_at": cooldown_ends_at,
            }

    return {"allowed": True, "reason_code": None, "reason": None, "next_at": current}


def eligible_senders(
    session: Session,
    group: SenderGroup,
    *,
    lock: bool = False,
    now: datetime | None = None,
) -> list[Sender]:
    eligible: list[Sender] = []
    candidates = connected_senders(group)
    if lock:
        candidate_ids = [sender.id for sender in candidates]
        candidates = list(
            session.scalars(
                select(Sender)
                .where(Sender.id.in_(candidate_ids))
                .order_by(Sender.id)
                .with_for_update()
            )
        ) if candidate_ids else []
    for sender in candidates:
        sender_reserved = sender_reserved_today(session, sender, now=now)
        if sender_sent_count_today(session, sender.id, now=now) + sender_reserved >= sender.daily_cap:
            continue
        current = _aware_utc(now or utcnow())
        if (
            sender.recent_error_at
            and current - _aware_utc(sender.recent_error_at) < SENDER_ERROR_COOLDOWN
        ):
            continue
        eligible.append(sender)
    return eligible


def serialize_sender(session: Session, sender: Sender) -> dict:
    sent_today = sender_sent_count_today(session, sender.id)
    return {
        "id": sender.id,
        "group_id": sender.group_id,
        "email": sender.email,
        "display_name": sender.display_name,
        "daily_cap": sender.daily_cap,
        "is_default": bool(sender.is_default),
        "status": sender.status,
        "connected_at": sender.connected_at.isoformat() if sender.connected_at else None,
        "revoked_at": sender.revoked_at.isoformat() if sender.revoked_at else None,
        "removed_at": sender.removed_at.isoformat() if sender.removed_at else None,
        "last_error": sender.last_error,
        "sent_today": sent_today,
        "daily_cap_remaining": max(sender.daily_cap - sent_today, 0),
    }


def serialize_group(session: Session, group: SenderGroup) -> dict:
    active_senders = [s for s in group.senders if s.status != "removed"]
    connected = [s for s in active_senders if s.status == "connected" and s.encrypted_oauth_credentials]
    return {
        "id": group.id,
        "name": group.name,
        "created_at": group.created_at.isoformat(),
        "updated_at": group.updated_at.isoformat(),
        "senders": [serialize_sender(session, sender) for sender in active_senders],
        "connected_sender_count": len(connected),
        "total_daily_cap": sum(sender.daily_cap for sender in connected),
        "error_sender_count": len([s for s in active_senders if s.status == "error"]),
    }


def upsert_connected_sender(
    session: Session,
    *,
    user_id: str,
    group_id: int,
    email: str,
    display_name: str,
    encrypted_credentials: str,
    scopes: Iterable[str],
) -> Sender:
    normalized = email.strip().lower()
    sender = session.scalar(select(Sender).where(Sender.user_id == user_id, Sender.email == normalized))
    now = utcnow()
    existing_default = session.scalar(
        select(Sender).where(Sender.user_id == user_id, Sender.is_default == 1, Sender.status != "removed")
    )
    if sender:
        sender.group_id = group_id
        sender.display_name = display_name or sender.display_name or ""
        sender.encrypted_oauth_credentials = encrypted_credentials
        sender.scopes = list(scopes)
        sender.status = "connected"
        sender.connected_at = now
        sender.revoked_at = None
        sender.removed_at = None
        sender.last_error = None
        sender.recent_error_at = None
        if not existing_default:
            sender.is_default = 1
    else:
        sender = Sender(
            user_id=user_id,
            group_id=group_id,
            email=normalized,
            display_name=display_name,
            encrypted_oauth_credentials=encrypted_credentials,
            scopes=list(scopes),
            status="connected",
            daily_cap=10,
            connected_at=now,
            is_default=1 if existing_default is None else 0,
        )
        session.add(sender)
    session.flush()
    return sender


def mark_sender_removed(sender: Sender) -> None:
    now = utcnow()
    sender.status = "removed"
    sender.encrypted_oauth_credentials = None
    sender.revoked_at = now
    sender.removed_at = now


def mark_oauth_state_used(state: OAuthState) -> None:
    state.used_at = utcnow()
