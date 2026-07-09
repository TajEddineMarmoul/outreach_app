from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user_id
from src.platform.db import get_session
from src.platform.models import Sender, SenderGroup
from src.platform.oauth import create_sender_oauth_start
from src.platform.services import ensure_user, mark_sender_removed, require_group, serialize_group, serialize_sender


router = APIRouter(prefix="/api/sender-groups", tags=["sender-groups"])
senders_router = APIRouter(prefix="/api/senders", tags=["senders"])


class SenderGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class SenderGroupPatch(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class SenderPatch(BaseModel):
    display_name: str | None = None
    daily_cap: int | None = Field(default=None, ge=1, le=500)
    group_id: int | None = None


@router.get("")
def list_sender_groups(
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    ensure_user(session, user_id)
    groups = list(
        session.scalars(
            select(SenderGroup)
            .options(selectinload(SenderGroup.senders))
            .where(SenderGroup.user_id == user_id)
            .order_by(SenderGroup.created_at, SenderGroup.id)
        )
    )
    return [serialize_group(session, group) for group in groups]


@router.post("")
def create_sender_group(
    req: SenderGroupCreate,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    ensure_user(session, user_id)
    group = SenderGroup(user_id=user_id, name=req.name.strip())
    session.add(group)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Sender group already exists")
    return serialize_group(session, group)


@router.patch("/{group_id}")
def patch_sender_group(
    group_id: int,
    req: SenderGroupPatch,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    try:
        group = require_group(session, user_id, group_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Sender group not found")
    group.name = req.name.strip()
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Sender group already exists")
    return serialize_group(session, group)


@senders_router.patch("/{sender_id}/default")
def set_sender_default(
    sender_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    sender = session.scalar(select(Sender).where(Sender.id == sender_id, Sender.user_id == user_id))
    if not sender or sender.status == "removed":
        raise HTTPException(status_code=404, detail="Sender not found")
    for s in session.scalars(select(Sender).where(Sender.user_id == user_id)):
        s.is_default = False
    sender.is_default = True
    session.commit()
    return serialize_sender(session, sender)


@router.delete("/{group_id}")
def delete_sender_group(
    group_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    try:
        group = require_group(session, user_id, group_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Sender group not found")
    active = [sender for sender in group.senders if sender.status != "removed"]
    if active:
        raise HTTPException(status_code=400, detail="Remove senders before deleting this group")
    for sender in list(group.senders):
        session.delete(sender)
    session.delete(group)
    session.commit()
    return {"status": "success"}


@router.get("/{group_id}/senders")
def list_group_senders(
    group_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    try:
        group = require_group(session, user_id, group_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Sender group not found")
    return [serialize_sender(session, sender) for sender in group.senders if sender.status != "removed"]


@router.post("/{group_id}/senders/oauth/start")
def start_group_sender_oauth(
    group_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    try:
        auth_url = create_sender_oauth_start(session, user_id=user_id, group_id=group_id)
        session.commit()
    except FileNotFoundError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError:
        session.rollback()
        raise HTTPException(status_code=404, detail="Sender group not found")
    return {"auth_url": auth_url}


@router.patch("/senders/{sender_id}")
def patch_sender(
    sender_id: int,
    req: SenderPatch,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    sender = session.scalar(select(Sender).where(Sender.id == sender_id, Sender.user_id == user_id))
    if not sender or sender.status == "removed":
        raise HTTPException(status_code=404, detail="Sender not found")
    if req.group_id is not None:
        try:
            require_group(session, user_id, req.group_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Sender group not found")
        sender.group_id = req.group_id
    if req.display_name is not None:
        sender.display_name = req.display_name
    if req.daily_cap is not None:
        sender.daily_cap = req.daily_cap
    session.commit()
    return serialize_sender(session, sender)


@router.delete("/senders/{sender_id}")
def delete_sender(
    sender_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    sender = session.scalar(select(Sender).where(Sender.id == sender_id, Sender.user_id == user_id))
    if not sender or sender.status == "removed":
        raise HTTPException(status_code=404, detail="Sender not found")
    mark_sender_removed(sender)
    session.commit()
    return {"status": "success"}


@senders_router.patch("/{sender_id}")
def patch_sender_canonical(
    sender_id: int,
    req: SenderPatch,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    return patch_sender(sender_id, req, session, user_id)


@senders_router.delete("/{sender_id}")
def delete_sender_canonical(
    sender_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    return delete_sender(sender_id, session, user_id)
