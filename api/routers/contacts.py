from __future__ import annotations

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

import json
from io import BytesIO
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field

from api.deps import db, get_db, get_current_user_id
from src.dnc import add_email as dnc_add_email, rows as dnc_rows
from src.importer import import_dataframe, normalize_email, is_do_not_contact

router = APIRouter()

class DNCAddRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ContactCreate(DNCAddRequest):
    first_name: str = Field(default="", max_length=200)
    last_name: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)


@router.get("/api/contacts/library")
def contact_library(search: str = Query(default="", max_length=200), campaign_id: int | None = None,
                    page: int = Query(default=1, ge=1), page_size: int = Query(default=6, ge=1, le=100),
                    conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    where = "c.user_id = ?"
    params = [user_id]
    if campaign_id is not None:
        if not db.get_campaign(conn, campaign_id, user_id):
            raise HTTPException(status_code=404, detail="Campaign not found")
        where += " AND EXISTS (SELECT 1 FROM campaign_recipients cr WHERE cr.contact_id = c.id AND cr.campaign_id = ?)"
        params.append(campaign_id)
    if search.strip():
        where += " AND (LOWER(c.email_normalized) LIKE ? OR LOWER(c.first_name) LIKE ? OR LOWER(c.last_name) LIKE ? OR LOWER(c.company_name) LIKE ?)"
        params.extend([f"%{search.strip().lower()}%"] * 4)
    total = conn.execute(f"SELECT COUNT(*) AS count FROM contacts c WHERE {where}", params).fetchone()["count"]
    rows = conn.execute(f"SELECT c.* FROM contacts c WHERE {where} ORDER BY c.id DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        fields = item.get("custom_fields") or {}
        if isinstance(fields, str):
            try:
                fields = json.loads(fields)
            except (ValueError, TypeError):
                fields = {}
        items.append({"id": item["id"], "email": item["email_normalized"], "first_name": item.get("first_name") or fields.get("first_name", ""),
                      "last_name": item.get("last_name") or fields.get("last_name", ""), "company": item.get("company_name") or fields.get("company", ""), "status": item["status"]})
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/api/contacts")
def create_contact(req: ContactCreate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    email = normalize_email(req.email)
    if db.fetch_contact_by_email(conn, email, user_id):
        raise HTTPException(status_code=409, detail="This contact is already saved")
    if is_do_not_contact(conn, email, user_id):
        raise HTTPException(status_code=422, detail="This email is on your do-not-contact list")
    result = import_dataframe(pd.DataFrame([{**req.model_dump(), "email": email}]), conn, user_id, source_type="manual")
    if result.errors:
        raise HTTPException(status_code=422, detail="; ".join(result.errors))
    return {"status": "success", **result.model_dump()}


@router.post("/api/contacts/import")
async def import_contacts(file: UploadFile = File(...), conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Choose a CSV smaller than 5 MB")
    try:
        frame = pd.read_csv(BytesIO(content), dtype=str, keep_default_na=False, nrows=10001)
    except (ValueError, UnicodeError, pd.errors.ParserError):
        raise HTTPException(status_code=422, detail="Could not read this CSV. Use a UTF-8 CSV with an email column.")
    if len(frame) > 10000:
        raise HTTPException(status_code=422, detail="Import up to 10,000 contacts at a time")
    result = import_dataframe(frame, conn, user_id)
    if result.errors:
        raise HTTPException(status_code=422, detail="; ".join(result.errors))
    return {"status": "success", **result.model_dump()}

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

