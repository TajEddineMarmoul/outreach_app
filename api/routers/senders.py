from __future__ import annotations

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.deps import db, get_db, get_current_user_id
from api.schemas import SenderUpdate, GroupCreate
from src.gmail_sender import connect_and_get_profile, connect_sender_account, credentials_file_path

router = APIRouter()


# ----------------------------------------------------
# 1. Campaigns Endpoints
# ----------------------------------------------------

@router.get("/api/senders")
def list_senders(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    senders = db.list_senders(conn, user_id)
    return [dict(sender) for sender in senders]

@router.post("/api/senders/connect")
def connect_sender(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    if not credentials_file_path().exists():
        raise HTTPException(status_code=400, detail="Gmail client credentials.json missing")
    try:
        connected = connect_sender_account(user_id, force_reauth=True)
        sender_id = db.upsert_sender(
            conn,
            email=connected.email,
            token_path=connected.token_path,
            user_id=user_id,
            display_name="Default sender",
            daily_cap=10,
            status="connected",
        )
        db.set_setting(conn, "sender_email", connected.email, user_id)
        return {"id": sender_id, "email": connected.email}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/api/senders/{sender_id}/reconnect")
def reconnect_sender(sender_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    sender = db.get_sender(conn, sender_id, user_id)
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    try:
        connected = connect_and_get_profile(
            force_reauth=True,
            token_path=Path(sender["token_path"]),
            prompt="select_account consent",
        )
        return {"status": "success", "email": connected.email}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.patch("/api/senders/{sender_id}")
def update_sender(sender_id: int, req: SenderUpdate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    sender = db.get_sender(conn, sender_id, user_id)
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    db.update_sender(conn, sender_id, user_id, req.display_name, req.daily_cap, req.group_name)
    return {"status": "success"}


@router.delete("/api/senders/{sender_id}")
def delete_sender(sender_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    sender = db.get_sender(conn, sender_id, user_id)
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    db.remove_sender(conn, sender_id, user_id)
    return {"status": "success"}


@router.post("/api/senders/{sender_id}/set-default")
def set_default_sender(sender_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    sender = db.get_sender(conn, sender_id, user_id)
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")
    db.set_default_sender(conn, sender_id, user_id)
    return {"status": "success"}


# ----------------------------------------------------
# 3b. Group Endpoints
# ----------------------------------------------------

@router.get("/api/groups")
def get_groups(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    saved = db.get_setting(conn, "sender_groups", [], user_id)
    db_groups = [
        row["group_name"]
        for row in conn.execute("SELECT DISTINCT group_name FROM senders WHERE user_id = ? AND group_name != ''", (user_id,)).fetchall()
    ]
    all_groups = sorted(set(saved + db_groups))
    return all_groups

@router.post("/api/groups")
def create_group(req: GroupCreate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    groups = db.get_setting(conn, "sender_groups", [], user_id)
    if req.name in groups:
        raise HTTPException(status_code=400, detail="Group already exists")
    groups.append(req.name)
    db.set_setting(conn, "sender_groups", sorted(groups), user_id)
    return {"status": "success"}

@router.delete("/api/groups/{group_name}")
def delete_group(group_name: str, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    groups = db.get_setting(conn, "sender_groups", [], user_id)
    if group_name not in groups:
        raise HTTPException(status_code=404, detail="Group not found")
    groups.remove(group_name)
    db.set_setting(conn, "sender_groups", groups, user_id)
    return {"status": "success"}


