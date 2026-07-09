from __future__ import annotations

import os, re
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from api.deps import db, get_db, get_current_user_id
from api.schemas import SenderUpdate, GroupCreate
from src.gmail_sender import SCOPES

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
    from src.gmail_sender import get_connected_email, sender_token_path_for_email

    safe_user = re.sub(r"[^a-zA-Z0-9._-]+", "_", user_id)
    token_dir = db.resolve_project_path(Path("tokens") / safe_user)
    if not token_dir.exists():
        raise HTTPException(status_code=400, detail="No Gmail tokens found. Complete the OAuth flow first (start → authorize → callback).")

    # Find the most recent token file
    token_files = sorted(token_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    token_path = next((f for f in token_files if f.name != "gmail_pending.json"), None)
    if not token_path:
        raise HTTPException(status_code=400, detail="No Gmail token found. Complete the OAuth flow first.")

    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    email = get_connected_email(creds)

    # Rename to the proper path
    proper_path = sender_token_path_for_email(email, user_id)
    if str(token_path) != str(proper_path):
        proper_path.parent.mkdir(parents=True, exist_ok=True)
        from shutil import move
        move(str(token_path), str(proper_path))
        token_path = proper_path

    sender_id = db.upsert_sender(
        conn,
        email=email,
        token_path=str(token_path),
        user_id=user_id,
        display_name="Default sender",
        daily_cap=10,
        status="connected",
    )
    db.set_setting(conn, "sender_email", email, user_id)
    return {"id": sender_id, "email": email}

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


