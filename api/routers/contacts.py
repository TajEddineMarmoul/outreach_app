from __future__ import annotations

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import db, get_db, get_current_user_id
from src.dnc import add_email as dnc_add_email, rows as dnc_rows

router = APIRouter()

class DNCAddRequest(BaseModel):
    email: str

@router.get("/api/contacts")
def list_global_contacts(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    contacts = db.fetch_contacts(conn, user_id)
    return [dict(contact) for contact in contacts]

@router.get("/api/contacts/dnc")
def list_dnc_emails(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    rows = dnc_rows(conn, user_id)
    return [dict(row) for row in rows]

@router.post("/api/contacts/dnc")
def add_dnc_email(req: DNCAddRequest, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    email = req.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email cannot be empty")
    dnc_add_email(conn, email, user_id)
    return {"status": "success"}



