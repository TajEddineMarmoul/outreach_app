from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.platform.models import (
    Campaign,
    Contact,
    OAuthState,
    Sender,
    SenderGroup,
    SendLog,
    User,
    UserSettings,
)
from src.platform.time import utcnow


CONNECTED_SENDER_STATUSES = {"connected"}


def ensure_user(session: Session, user_id: str, email: str | None = None) -> User:
    user = session.get(User, user_id)
    if user:
        if email and user.email != email:
            user.email = email
        return user
    user = User(id=user_id, email=email)
    session.add(user)
    session.add(UserSettings(user_id=user_id))
    session.flush()
    return user


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
    return [sender for sender in group.senders if sender.status == "connected" and sender.encrypted_oauth_credentials]


def sender_sent_count_today(session: Session, sender_id: int) -> int:
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        session.scalar(
            select(func.count())
            .select_from(SendLog)
            .where(
                SendLog.sender_id == sender_id,
                SendLog.status.in_(("sent", "test_sent")),
                SendLog.sent_at >= start,
            )
        )
        or 0
    )


def eligible_senders(session: Session, group: SenderGroup) -> list[Sender]:
    eligible: list[Sender] = []
    for sender in connected_senders(group):
        if sender_sent_count_today(session, sender.id) >= sender.daily_cap:
            continue
        if sender.recent_error_at and utcnow() - sender.recent_error_at < timedelta(minutes=15):
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
        select(Sender).where(Sender.user_id == user_id, Sender.is_default == True, Sender.status != "removed")
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
            sender.is_default = True
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
            is_default=existing_default is None,
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

