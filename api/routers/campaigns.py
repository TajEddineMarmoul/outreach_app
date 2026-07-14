from __future__ import annotations

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

import sys
import json
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict
import pandas as pd
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from api.deps import PROJECT_ROOT, db, config_path, get_db, get_current_user_id
from api.schemas import (
    CampaignCreate,
    CampaignUpdate,
    ComposerUpdate,
    SenderSelect,
    RecipientsPaste,
    RecipientsGoogleSheet,
    RecipientsSelectExisting,
    TestSendRequest,
    SenderUpdate,
)
from src.models import AppConfig, load_config, save_config, ContactStatus
from src.gmail_sender import gmail_connection_status
from src.google_sheets import get_public_sheet_csv, get_published_csv, list_public_sheet_tabs, parse_google_sheet_url_details
from src.importer import import_dataframe, normalize_email, detect_columns
from src.safety import campaign_checklist
from src.scheduler import send_test_email
from src.analytics import send_log_dataframe

router = APIRouter()

EDIT_LOCKED_STATUSES = {"sending", "scheduled", "autopilot", "paused"}


def require_editable_campaign(conn, campaign_id: int, user_id: str):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if str(campaign["status"]) in EDIT_LOCKED_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Stop the campaign before editing its composer, send options, or recipients",
        )
    return campaign


# ----------------------------------------------------
# 1. Campaigns Endpoints
# ----------------------------------------------------

@router.get("/api/campaigns")
def list_campaigns(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaigns = db.list_campaigns(conn, user_id)
    result = []
    for row in campaigns:
        d = dict(row)
        cnt = conn.execute(
            "SELECT COUNT(*) AS count FROM campaign_recipients WHERE campaign_id = ?",
            (d["id"],)
        ).fetchone()["count"]
        d["recipient_count"] = cnt
        result.append(d)
    return result

@router.post("/api/campaigns")
def create_campaign(req: CampaignCreate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Campaign name cannot be empty")
    campaign_id = db.create_campaign(conn, user_id, req.name.strip())
    return {"id": campaign_id, "name": req.name}

@router.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    res = dict(campaign)
    res["require_attachment"] = db.get_setting(conn, f"campaign_{campaign_id}_require_attachment", "false") == "true"
    res["tracking_enabled"] = db.get_setting(conn, f"campaign_{campaign_id}_tracking_enabled", "true") == "true"
    res["unsubscribe_link"] = db.get_setting(conn, f"campaign_{campaign_id}_unsubscribe_link", "true") == "true"
    return res

@router.patch("/api/campaigns/{campaign_id}")
def update_campaign(campaign_id: int, req: CampaignUpdate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = require_editable_campaign(conn, campaign_id, user_id)
    
    name = req.name if req.name is not None else str(campaign["name"])
    subject = req.subject_template if req.subject_template is not None else str(campaign["subject_template"])
    body = req.body_template if req.body_template is not None else str(campaign["body_template"])
    fallback = req.fallback_body_template if req.fallback_body_template is not None else str(campaign["fallback_body_template"])
    attachment = req.attachment_path if req.attachment_path is not None else str(campaign["attachment_path"] or "")

    db.update_campaign_name(conn, campaign_id, user_id, name)
    db.update_campaign(conn, campaign_id, user_id, subject, body, fallback, attachment)
    
    if req.require_attachment is not None:
        db.set_setting(conn, f"campaign_{campaign_id}_require_attachment", "true" if req.require_attachment else "false", user_id)
    if req.tracking_enabled is not None:
        db.set_setting(conn, f"campaign_{campaign_id}_tracking_enabled", "true" if req.tracking_enabled else "false", user_id)
    if req.unsubscribe_link is not None:
        db.set_setting(conn, f"campaign_{campaign_id}_unsubscribe_link", "true" if req.unsubscribe_link else "false", user_id)
        
    return {"status": "success"}

@router.delete("/api/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = require_editable_campaign(conn, campaign_id, user_id)
    from sqlalchemy import delete as sa_delete, select
    from src.platform.db import SessionLocal
    from src.platform.models import (
        AutopilotDaySchedule,
        Campaign as PlatformCampaign,
        CampaignRecipient as PlatformCampaignRecipient,
        SendJob,
        SendLog as PlatformSendLog,
    )
    platform_session = SessionLocal()
    try:
        platform_campaign = platform_session.scalar(
            select(PlatformCampaign).where(
                PlatformCampaign.id == campaign_id,
                PlatformCampaign.user_id == user_id,
            )
        )
        if platform_campaign:
            platform_session.execute(sa_delete(SendJob).where(SendJob.campaign_id == campaign_id))
            platform_session.execute(
                sa_delete(AutopilotDaySchedule).where(AutopilotDaySchedule.campaign_id == campaign_id)
            )
            platform_session.execute(sa_delete(PlatformSendLog).where(PlatformSendLog.campaign_id == campaign_id))
            platform_session.execute(
                sa_delete(PlatformCampaignRecipient).where(
                    PlatformCampaignRecipient.campaign_id == campaign_id
                )
            )
            platform_session.delete(platform_campaign)
            platform_session.commit()
    finally:
        platform_session.close()
    db.delete_campaign(conn, campaign_id, user_id)
    return {"status": "success"}


# ----------------------------------------------------
# 2. Campaign Editor Endpoints
# ----------------------------------------------------

@router.get("/api/campaigns/{campaign_id}/summary")
def get_campaign_summary(campaign_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    config = load_config(config_path())
    sender_group_name = None
    sender_group_id = None
    sender_group_capacity = None
    sender_emails: list[str] = []
    send_settings: dict = {}
    autopilot_schedule: list[dict] = []
    user_timezone = "UTC"
    try:
        from sqlalchemy import select
        from sqlalchemy.exc import SQLAlchemyError
        from src.platform.db import SessionLocal
        from src.platform.models import AutopilotDaySchedule, Campaign as PlatformCampaign
        from src.platform.services import require_group, serialize_group, user_zone

        platform_session = SessionLocal()
        try:
            user_timezone = user_zone(platform_session, user_id).key
            platform_campaign = platform_session.scalar(
                select(PlatformCampaign).where(PlatformCampaign.id == campaign_id, PlatformCampaign.user_id == user_id)
            )
            if platform_campaign:
                send_settings = dict(platform_campaign.send_settings or {})
                autopilot_schedule = [
                    {
                        "day": item.day_of_week,
                        "cap": item.daily_cap,
                        "start": item.start_time,
                        "end": item.end_time,
                    }
                    for item in platform_session.scalars(
                        select(AutopilotDaySchedule).where(
                            AutopilotDaySchedule.campaign_id == platform_campaign.id
                        )
                    )
                ]
            if platform_campaign and platform_campaign.selected_sender_group_id:
                group = require_group(platform_session, user_id, platform_campaign.selected_sender_group_id)
                group_payload = serialize_group(platform_session, group)
                sender_group_id = group.id
                sender_group_name = group.name
                sender_group_capacity = group_payload
                sender_emails = [
                    sender.email
                    for sender in group.senders
                    if sender.status == "connected" and sender.encrypted_oauth_credentials
                ]
        finally:
            platform_session.close()
    except Exception:
        pass
    
    status = str(campaign["status"])
    recipient_count = db.campaign_contact_count(conn, campaign_id)
    
    att_path = str(campaign["attachment_path"] or config.campaign.attachment_path or "")
    att_resolved = db.resolve_project_path(att_path) if att_path else None
    att_exists = bool(att_resolved and att_resolved.exists())
    att_label = Path(att_path).name if att_exists else "none"

    schedule_label = "not set"
    if status == "scheduled":
        days_short = ", ".join(d[:3].title() for d in config.sending.days)
        schedule_label = f"{days_short} {config.sending.start_time}-{config.sending.end_time}"
        
    require_attachment = db.get_setting(conn, f"campaign_{campaign_id}_require_attachment", "false", user_id) == "true"
    tracking_enabled = db.get_setting(conn, f"campaign_{campaign_id}_tracking_enabled", "true", user_id) == "true"
    unsubscribe_link = db.get_setting(conn, f"campaign_{campaign_id}_unsubscribe_link", "true", user_id) == "true"

    sheet_contacts = conn.execute(
        "SELECT COUNT(*) AS cnt FROM contacts c INNER JOIN campaign_recipients cr ON cr.contact_id = c.id WHERE cr.campaign_id = ? AND c.source_type = 'google_sheet'",
        (campaign_id,),
    ).fetchone()
    sheet_synced = (sheet_contacts["cnt"] or 0) > 0

    return {
        "sender": sender_group_name,
        "sender_group_name": sender_group_name,
        "sender_group_id": sender_group_id,
        "sender_group_capacity": sender_group_capacity,
        "sender_emails": sender_emails,
        "recipients": recipient_count,
        "mode": status,
        "attachment": att_label,
        "daily_cap": config.sending.daily_cap,
        "schedule": schedule_label,
        "require_attachment": require_attachment,
        "tracking_enabled": tracking_enabled,
        "unsubscribe_link": unsubscribe_link,
        "sheet_synced": sheet_synced,
        "send_settings": send_settings,
        "autopilot_schedule": autopilot_schedule,
        "timezone": user_timezone,
    }

@router.patch("/api/campaigns/{campaign_id}/composer")
def patch_composer(campaign_id: int, req: ComposerUpdate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = require_editable_campaign(conn, campaign_id, user_id)
    
    db.update_campaign(
        conn,
        campaign_id,
        user_id,
        req.subject_template,
        req.body_template,
        req.fallback_body_template,
        str(campaign["attachment_path"] or ""),
    )
    db.clear_campaign_previews(conn, campaign_id, user_id)
    db.set_setting(conn, f"campaign_{campaign_id}_template_saved", True, user_id)
    db.set_setting(conn, f"campaign_{campaign_id}_test_sent", False, user_id)
    db.set_setting(conn, f"campaign_{campaign_id}_require_attachment", "true" if req.require_attachment else "false", user_id)
    
    config = load_config(config_path())
    config.campaign.attachment_path = str(campaign["attachment_path"] or "")
    save_config(config, config_path())
    
    return {"status": "success"}

@router.post("/api/campaigns/{campaign_id}/attachment")
async def post_attachment(campaign_id: int, file: UploadFile = File(...), conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = require_editable_campaign(conn, campaign_id, user_id)
        
    upload_dir = PROJECT_ROOT / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / file.filename
    content = await file.read()
    file_path.write_bytes(content)
    
    relative_path = str(file_path.relative_to(PROJECT_ROOT))
    db.update_campaign(
        conn,
        campaign_id,
        user_id,
        str(campaign["subject_template"]),
        str(campaign["body_template"]),
        str(campaign["fallback_body_template"]),
        relative_path,
    )
    
    return {"filename": file.filename, "path": relative_path}

@router.delete("/api/campaigns/{campaign_id}/attachment")
def delete_attachment(campaign_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = require_editable_campaign(conn, campaign_id, user_id)
        
    db.update_campaign(
        conn,
        campaign_id,
        user_id,
        str(campaign["subject_template"]),
        str(campaign["body_template"]),
        str(campaign["fallback_body_template"]),
        "",
    )
    return {"status": "success"}


# ----------------------------------------------------
# 3. Senders Endpoints
# ----------------------------------------------------

@router.patch("/api/campaigns/{campaign_id}/sender")
def patch_campaign_sender(campaign_id: int, req: SenderSelect, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = require_editable_campaign(conn, campaign_id, user_id)
    db.set_campaign_sender(conn, campaign_id, req.sender_id, user_id)
    return {"status": "success"}


@router.get("/api/senders")
def list_senders(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    senders = db.list_senders(conn, user_id)
    return [dict(s) for s in senders]


def resolve_import_mapping(df: pd.DataFrame, mapping: dict | None = None) -> dict[str, str]:
    resolved = detect_columns(list(df.columns))
    for field, column in (mapping or {}).items():
        if not isinstance(column, str) or column not in df.columns:
            raise HTTPException(
                status_code=422,
                detail=f"Mapped column '{column}' for '{field}' was not found in the import",
            )
        resolved[field] = column
    if "email" not in resolved:
        raise HTTPException(status_code=422, detail="The import must contain an email column")
    return resolved


def import_and_attach_df(conn, campaign_id: int, df: pd.DataFrame, mapping: dict | None, source_type: str, url: str = "", user_id: str = "default_user"):
    if df.empty:
        raise HTTPException(status_code=422, detail="The import contains no recipient rows")

    resolved_mapping = resolve_import_mapping(df, mapping)
    result = import_dataframe(
        df,
        conn,
        user_id=user_id,
        column_mapping=resolved_mapping,
        source_type=source_type,
        source_url=url,
    )
    if result.errors:
        raise HTTPException(status_code=422, detail="; ".join(result.errors))

    email_column = resolved_mapping["email"]
    emails = list(
        dict.fromkeys(
            email
            for value in df[email_column].tolist()
            if (email := normalize_email(value))
        )
    )
    attached = db.add_campaign_recipients_by_emails(conn, campaign_id, emails, user_id)
    return {**result.model_dump(), "attached": attached}

@router.post("/api/campaigns/{campaign_id}/recipients/csv")
async def post_recipients_csv(
    campaign_id: int,
    file: UploadFile = File(...),
    mapping_json: str = Form(...),
    conn=Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    campaign = require_editable_campaign(conn, campaign_id, user_id)
        
    try:
        mapping = json.loads(mapping_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Invalid column mapping") from exc
    if not isinstance(mapping, dict):
        raise HTTPException(status_code=422, detail="Column mapping must be an object")

    content = await file.read()
    try:
        df = pd.read_csv(StringIO(content.decode("utf-8-sig")))
    except (UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not read CSV: {exc}") from exc
    
    res = import_and_attach_df(conn, campaign_id, df, mapping, "csv", file.filename or "", user_id)
    return res

@router.post("/api/campaigns/{campaign_id}/recipients/paste")
def post_recipients_paste(campaign_id: int, req: RecipientsPaste, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = require_editable_campaign(conn, campaign_id, user_id)
        
    try:
        df = pd.read_csv(StringIO(req.raw))
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not read pasted recipients: {exc}") from exc
    res = import_and_attach_df(conn, campaign_id, df, None, "paste", user_id=user_id)
    return res

@router.post("/api/campaigns/{campaign_id}/recipients/google-sheet")
def post_recipients_sheet(campaign_id: int, req: RecipientsGoogleSheet, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = require_editable_campaign(conn, campaign_id, user_id)
        
    sheet_url = req.url
    tab_name = req.tab_name
    header_row = req.header_row
    use_private = req.use_private
    mapping = req.mapping
    if use_private:
        raise HTTPException(status_code=400, detail="Private Google Sheets import is not supported. Use a public or published sheet link.")
    
    # Load sheet rows
    if "output=csv" in sheet_url or "/pub?" in sheet_url or "format=csv" in sheet_url:
        df = get_published_csv(sheet_url, header_row=header_row)
    else:
        sheet = parse_google_sheet_url_details(sheet_url)
        df = get_public_sheet_csv(
            sheet.sheet_id,
            gid=sheet.gid,
            header_row=header_row,
            sheet_name=tab_name.strip() or None,
        )
            
    res = import_and_attach_df(conn, campaign_id, df, mapping, "google_sheet", sheet_url, user_id)
    return res

@router.post("/api/campaigns/{campaign_id}/recipients/select-existing")
def post_recipients_select_existing(campaign_id: int, req: RecipientsSelectExisting, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = require_editable_campaign(conn, campaign_id, user_id)
    
    requested_ids = [int(cid) for cid in req.contact_ids]
    placeholders = ",".join("?" for _ in requested_ids)
    valid_contact_ids = {
        int(row["id"])
        for row in conn.execute(
            f"SELECT id FROM contacts WHERE user_id = ? AND id IN ({placeholders})",
            [user_id, *requested_ids],
        ).fetchall()
    } if requested_ids else set()
    attached = 0
    for cid in valid_contact_ids:
        # Check if recipient already exists
        count = conn.execute(
            "SELECT COUNT(*) AS count FROM campaign_recipients WHERE campaign_id = ? AND contact_id = ?",
            (campaign_id, cid)
        ).fetchone()["count"]
        if count == 0:
            contact = conn.execute(
                "SELECT status FROM contacts WHERE id = ? AND user_id = ?",
                (cid, user_id),
            ).fetchone()
            if not contact:
                continue
            conn.execute(
                "INSERT INTO campaign_recipients (campaign_id, contact_id, status, created_at) VALUES (?, ?, ?, ?)",
                (campaign_id, cid, contact["status"] or "pending", db.utcnow_iso())
            )
            attached += 1
    conn.commit()
    return {"attached": attached}


@router.get("/api/campaigns/{campaign_id}/validation-summary")
def get_campaign_validation_summary(campaign_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    contacts = db.campaign_contacts(conn, campaign_id, user_id)
    total_contacts = len(contacts)
    
    if total_contacts == 0:
        return {
            "total_contacts": 0,
            "used_warnings": [],
            "other_warnings": [],
            "all_columns": []
        }
        
    import json
    
    # Initialize dictionary to accumulate empty counts for every field we see
    column_empty_counts = {}

    for c in contacts:
        c = dict(c)
        custom_str = c.get("custom_fields") or "{}"
        try:
            custom_data = custom_str if isinstance(custom_str, dict) else json.loads(custom_str)
        except Exception:
            custom_data = {}

        for key, val in custom_data.items():
            if key not in column_empty_counts:
                column_empty_counts[key] = 0
            if val is None or str(val).strip() == "":
                column_empty_counts[key] += 1
                
    from src.template_engine import sanitize_template_variables
    from jinja2 import Environment, meta
    
    ENV = Environment()
    used_vars = set()
    for template_str in [campaign["subject_template"], campaign["body_template"]]:
        if template_str:
            try:
                sanitized = sanitize_template_variables(str(template_str))
                parsed = ENV.parse(sanitized)
                used_vars.update(meta.find_undeclared_variables(parsed))
            except Exception:
                pass
                
    if "keyword_sentence" in used_vars:
        used_vars.add("keyword_1")
        used_vars.add("keyword_2")
        used_vars.add("keyword_3")
        
    used_warnings = []
    other_warnings = []
    
    for key, empty_count in column_empty_counts.items():
        if empty_count > 0:
            item = {"column": key, "empty_count": empty_count}
            if key in used_vars:
                used_warnings.append(item)
            else:
                other_warnings.append(item)
                
    return {
        "total_contacts": total_contacts,
        "used_warnings": used_warnings,
        "other_warnings": other_warnings,
        "all_columns": sorted(list(column_empty_counts.keys()))
    }


# ----------------------------------------------------
# 5. Preview & Test Endpoints
# ----------------------------------------------------

@router.get("/api/campaigns/{campaign_id}/preview")
def get_campaign_preview(campaign_id: int, limit: int = 1000, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    att_name = ""
    if campaign and campaign["attachment_path"]:
        from pathlib import Path
        att_name = Path(str(campaign["attachment_path"])).name

    contacts = db.campaign_contacts(conn, campaign_id, user_id, limit=limit)
    res = []
    for c in contacts:
        res.append({
            "id": c["id"],
            "recipient_email": c["email"],
            "first_name": c["first_name"],
            "subject": c["last_preview_subject"],
            "body": c["last_preview_body"],
            "generated_at": c["preview_generated_at"],
            "attachment_name": att_name
        })
    return res

@router.post("/api/campaigns/{campaign_id}/preview/generate")
def post_generate_previews(campaign_id: int, limit: Optional[int] = None, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    from src.preview import generate_preview
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    contacts = db.campaign_contacts(conn, campaign_id, user_id, limit=limit)
    count = 0
    now = db.utcnow_iso()
    for c in contacts:
        preview = generate_preview(conn, int(c["id"]), user_id, campaign_id=campaign_id, mark=False)
        conn.execute(
            """
            UPDATE contacts
            SET preview_generated_at = ?, last_preview_subject = ?, last_preview_body = ?,
                updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (now, preview.subject, preview.body, now, int(c["id"]), user_id),
        )
        count += 1
    conn.commit()
    return {
        "generated": count,
    }

class RejectRecipientsRequest(BaseModel):
    contact_ids: list[int]

@router.post("/api/campaigns/{campaign_id}/recipients/reject")
def post_reject_recipients(campaign_id: int, req: RejectRecipientsRequest, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    from src.preview import reject_contacts
    campaign = require_editable_campaign(conn, campaign_id, user_id)
    requested_ids = [int(contact_id) for contact_id in req.contact_ids]
    placeholders = ",".join("?" for _ in requested_ids)
    attached_ids = {
        int(row["contact_id"])
        for row in conn.execute(
            f"SELECT contact_id FROM campaign_recipients WHERE campaign_id = ? AND contact_id IN ({placeholders})",
            [campaign_id, *requested_ids],
        ).fetchall()
    } if requested_ids else set()
    rejected = reject_contacts(conn, list(attached_ids), user_id)
    db.set_contacts_status(conn, attached_ids, "rejected", user_id)
    if attached_ids:
        placeholders = ",".join("?" for _ in attached_ids)
        conn.execute(
            f"UPDATE campaign_recipients SET status = 'rejected' WHERE campaign_id = ? AND contact_id IN ({placeholders})",
            [campaign_id, *attached_ids],
        )
        conn.commit()
    return {"rejected": rejected}

@router.post("/api/campaigns/{campaign_id}/test-send")
def post_test_send(campaign_id: int, req: TestSendRequest, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    contact_id = req.preview_contact_id
    if contact_id is None:
        contact = next(iter(db.campaign_contacts(conn, campaign_id, user_id, limit=1)), None)
        if not contact:
            raise HTTPException(status_code=400, detail="No campaign preview contact found")
        contact_id = int(contact["id"])
    else:
        belongs = conn.execute(
            """
            SELECT 1
            FROM campaign_recipients
            WHERE campaign_id = ? AND contact_id = ?
            """,
            (campaign_id, contact_id),
        ).fetchone()
        if not belongs:
            raise HTTPException(status_code=400, detail="Preview contact is not attached to this campaign")

    config = load_config(config_path())
    success, msg = send_test_email(conn, contact_id, req.recipient_email, config, campaign_id=campaign_id, user_id=user_id)
    if msg == "No Gmail sender selected":
        try:
            from datetime import datetime, timezone
            from sqlalchemy import select
            from src.platform.db import SessionLocal
            from src.platform.models import Sender as PlatformSender, SendLog as PlatformSendLog
            from src.platform.gmail import gmail_service_for_sender
            from src.gmail_sender import send_email as gmail_send
            from src.preview import generate_preview

            platform_session = SessionLocal()
            try:
                from src.platform.models import Campaign as PlatformCampaign
                platform_campaign = platform_session.scalar(
                    select(PlatformCampaign).where(
                        PlatformCampaign.id == campaign_id,
                        PlatformCampaign.user_id == user_id,
                    )
                )
                if not platform_campaign or not platform_campaign.selected_sender_group_id:
                    raise HTTPException(status_code=400, detail="Campaign has no sender group selected")
                platform_sender = platform_session.scalar(
                    select(PlatformSender).where(
                        PlatformSender.user_id == user_id,
                        PlatformSender.group_id == platform_campaign.selected_sender_group_id,
                        PlatformSender.status == "connected",
                    ).order_by(PlatformSender.is_default.desc(), PlatformSender.id).limit(1)
                )
                if not platform_sender:
                    raise HTTPException(status_code=400, detail="No connected Gmail sender found")
                rendered = generate_preview(conn, contact_id, user_id, campaign_id=campaign_id, mark=False)
                result = gmail_send(
                    sender=platform_sender.email,
                    recipient=req.recipient_email,
                    subject=rendered.subject,
                    body=rendered.body,
                    service=gmail_service_for_sender(platform_session, platform_sender),
                )
                log = PlatformSendLog(
                    user_id=user_id,
                    campaign_id=campaign_id,
                    sender_id=platform_sender.id,
                    recipient_email=req.recipient_email,
                    sender_email=platform_sender.email,
                    subject=rendered.subject,
                    body_snapshot=rendered.body,
                    status="test_sent",
                    sent_at=datetime.now(timezone.utc),
                    gmail_message_id=result.message_id,
                    gmail_thread_id=result.thread_id,
                )
                platform_session.add(log)
                platform_session.commit()
            finally:
                platform_session.close()
            db.set_setting(conn, f"campaign_{campaign_id}_test_sent", True, user_id)
            return {"status": "success", "detail": "Test email sent"}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    
    db.set_setting(conn, f"campaign_{campaign_id}_test_sent", True, user_id)
    return {"status": "success", "detail": msg}


# ----------------------------------------------------
# 6. Sending Flow Endpoints
# ----------------------------------------------------

def run_preflight(conn, config, campaign, user_id="default_user"):
    selected_sender = db.get_campaign_sender(conn, int(campaign["id"]), user_id)
    sender_status = (
        gmail_connection_status(token_path=selected_sender["token_path"])
        if selected_sender
        else gmail_connection_status(token_path="tokens/missing.json")
    )
    checklist = campaign_checklist(conn, config, campaign, sender_status)
    missing = [label for label, ok in checklist.items() if not ok]
    
    # Validation checks
    block_items = []
    if not checklist.get("Gmail connected", False):
        block_items.append("Sender missing")
    if not checklist.get("Recipients selected", False) or not checklist.get("Approved recipients", False):
        block_items.append("Recipients missing or none approved")
    if not checklist.get("Preview generated", False):
        block_items.append("Preview not generated")
    if not checklist.get("Test sent", False):
        block_items.append("Test not sent")
        
    if block_items:
        raise HTTPException(status_code=400, detail={"msg": "Preflight validation failed", "blocks": block_items})

# ----------------------------------------------------
# 7. Logs Endpoints
# ----------------------------------------------------

@router.get("/api/campaigns/{campaign_id}/logs")
def get_campaign_logs(campaign_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    log = send_log_dataframe(conn, user_id=user_id, campaign_id=campaign_id)
    return log.to_dict(orient="records")

@router.get("/api/campaigns/{campaign_id}/logs/export")
def get_logs_export(campaign_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    log = send_log_dataframe(conn, user_id=user_id, campaign_id=campaign_id)
    temp_file = PROJECT_ROOT / "data" / f"campaign_{campaign_id}_log.csv"
    log.to_csv(temp_file, index=False)
    return FileResponse(path=str(temp_file), filename=f"campaign_{campaign_id}_send_log.csv", media_type="text/csv")


# ----------------------------------------------------
# 8. Settings & OAuth Endpoints
# ----------------------------------------------------

@router.get("/api/google-sheets/public-tabs")
def get_public_google_sheet_tabs(url: str = Query(...)):
    try:
        return {"tabs": list_public_sheet_tabs(url)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not load public sheet tabs: {str(exc)}")

@router.get("/api/logs")
def get_global_logs(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    log = send_log_dataframe(conn, user_id=user_id)
    return log.fillna('').to_dict(orient="records")
