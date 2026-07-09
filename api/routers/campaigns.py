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

from api.deps import PROJECT_ROOT, db, get_db_path, config_path, get_db, get_current_user_id
from api.schemas import (
    CampaignCreate,
    CampaignUpdate,
    ComposerUpdate,
    SendSettingsUpdate,
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
from src.scheduler import start_background_autopilot, stop_autopilot, send_test_email, bulk_send_approved
from src.analytics import send_log_dataframe

router = APIRouter()


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
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
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
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
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
    selected_sender = db.get_campaign_sender(conn, campaign_id, user_id)
    sender_group = str(selected_sender["group_name"]) if (selected_sender and selected_sender["group_name"]) else None
    sender_email = str(selected_sender["email"]) if selected_sender else None
    
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
        "sender": sender_group,
        "sender_email": sender_email,
        "recipients": recipient_count,
        "mode": status,
        "attachment": att_label,
        "daily_cap": config.sending.daily_cap,
        "schedule": schedule_label,
        "require_attachment": require_attachment,
        "tracking_enabled": tracking_enabled,
        "unsubscribe_link": unsubscribe_link,
        "sheet_synced": sheet_synced,
    }

@router.patch("/api/campaigns/{campaign_id}/composer")
def patch_composer(campaign_id: int, req: ComposerUpdate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
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

@router.patch("/api/campaigns/{campaign_id}/send-settings")
def patch_send_settings(campaign_id: int, req: SendSettingsUpdate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    config = load_config(config_path())
    config.sending.days = req.days
    config.sending.start_time = req.start_time
    config.sending.end_time = req.end_time
    config.sending.daily_cap = req.daily_cap
    config.sending.delay_minutes = req.delay_minutes
    save_config(config, config_path())
    
    selected_sender = db.get_campaign_sender(conn, campaign_id, user_id)
    if selected_sender and req.sender_daily_cap is not None:
        db.update_sender_daily_cap(conn, int(selected_sender["id"]), req.sender_daily_cap, user_id)
        
    return {"status": "success"}

@router.post("/api/campaigns/{campaign_id}/attachment")
async def post_attachment(campaign_id: int, file: UploadFile = File(...), conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
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
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
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
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.set_campaign_sender(conn, campaign_id, req.sender_id, user_id)
    return {"status": "success"}


@router.get("/api/campaigns/{campaign_id}/recipients")
def get_campaign_recipients(campaign_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    contacts = db.campaign_contacts(conn, campaign_id, user_id)
    return [dict(contact) for contact in contacts]

def import_and_attach_df(conn, campaign_id: int, df: pd.DataFrame, mapping: dict, source_type: str, url: str = "", user_id: str = "default_user"):
    result = import_dataframe(
        df,
        conn,
        user_id=user_id,
        column_mapping=mapping,
        source_type=source_type,
        source_url=url,
    )
    # Extract emails
    email_column = mapping.get("email")
    emails = []
    if email_column and email_column in df.columns:
        emails = [normalize_email(val) for val in df[email_column].tolist() if normalize_email(val)]
    attached = db.add_campaign_recipients_by_emails(conn, campaign_id, emails, user_id)
    return {"imported": result.imported, "attached": attached}

@router.post("/api/campaigns/{campaign_id}/recipients/csv")
async def post_recipients_csv(
    campaign_id: int,
    file: UploadFile = File(...),
    mapping_json: str = Form(...),
    conn=Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    mapping = json.loads(mapping_json)
    content = await file.read()
    df = pd.read_csv(StringIO(content.decode("utf-8")))
    
    res = import_and_attach_df(conn, campaign_id, df, mapping, "csv", file.filename, user_id)
    return res

@router.post("/api/campaigns/{campaign_id}/recipients/paste")
def post_recipients_paste(campaign_id: int, req: RecipientsPaste, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    df = pd.read_csv(StringIO(req.raw))
    mapping = detect_columns(list(df.columns))
    res = import_and_attach_df(conn, campaign_id, df, mapping, "paste", user_id=user_id)
    return res

@router.post("/api/campaigns/{campaign_id}/recipients/google-sheet")
def post_recipients_sheet(campaign_id: int, req: RecipientsGoogleSheet, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
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
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    attached = 0
    for cid in req.contact_ids:
        # Check if recipient already exists
        count = conn.execute(
            "SELECT COUNT(*) AS count FROM campaign_recipients WHERE campaign_id = ? AND contact_id = ?",
            (campaign_id, cid)
        ).fetchone()["count"]
        if count == 0:
            conn.execute(
                "INSERT INTO campaign_recipients (campaign_id, contact_id, created_at) VALUES (?, ?, ?)",
                (campaign_id, cid, db.utcnow_iso())
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
            custom_data = json.loads(custom_str)
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
    contacts = db.campaign_contacts(conn, campaign_id, user_id, limit=limit)
    count = 0
    now = db.utcnow_iso()
    first_body = None
    first_subject = None
    for c in contacts:
        preview = generate_preview(conn, int(c["id"]), campaign_id=campaign_id, mark=False)
        if count == 0:
            first_body = preview.body
            first_subject = preview.subject
            print(f"DEBUG GENERATE ID 1: subject={preview.subject!r}, body_len={len(preview.body or '')}, body={preview.body!r}")
        conn.execute(
            """
            UPDATE contacts
            SET preview_generated_at = ?, last_preview_subject = ?, last_preview_body = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now, preview.subject, preview.body, now, int(c["id"])),
        )
        count += 1
    conn.commit()
    return {
        "generated": count,
        "debug_first_subject": first_subject,
        "debug_first_body": first_body,
    }

class ApproveRecipientsRequest(BaseModel):
    contact_ids: Optional[list[int]] = None

@router.post("/api/campaigns/{campaign_id}/recipients/approve")
def post_approve_recipients(campaign_id: int, req: ApproveRecipientsRequest, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    from src.preview import approve_contacts
    if req.contact_ids is not None:
        approved = approve_contacts(conn, req.contact_ids)
    else:
        pending = [
            row["id"] for row in db.campaign_contacts(conn, campaign_id, user_id, statuses=("pending",))
            if row["preview_generated_at"] is not None
        ]
        approved = approve_contacts(conn, pending)
    return {"approved": approved}

class RejectRecipientsRequest(BaseModel):
    contact_ids: list[int]

@router.post("/api/campaigns/{campaign_id}/recipients/reject")
def post_reject_recipients(campaign_id: int, req: RejectRecipientsRequest, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    from src.preview import reject_contacts
    rejected = reject_contacts(conn, req.contact_ids)
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
    success, msg = send_test_email(conn, contact_id, req.recipient_email, config, campaign_id=campaign_id)
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

class BulkSendRequest(BaseModel):
    delay_minutes: int = 5

class BulkScheduleRequest(BaseModel):
    delay_minutes: int = 5
    scheduled_at: str = ""  # ISO datetime

class AutopilotStartRequest(BaseModel):
    days: Optional[List[str]] = None
    start_time: str = "09:00"
    end_time: str = "17:00"
    daily_cap: int = 10
    delay_minutes: int = 5
    scheduled_at: str = ""  # ISO datetime

@router.post("/api/campaigns/{campaign_id}/send-now")
def post_send_now(campaign_id: int, req: BulkSendRequest = BulkSendRequest(), conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    import threading

    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    config = load_config(config_path())
    run_preflight(conn, config, campaign, user_id)

    db.set_campaign_status(conn, "sending", campaign_id, user_id)

    def _run():
        c = db.init_db(get_db_path())
        cfg = load_config(config_path())
        bulk_send_approved(c, campaign_id, cfg, req.delay_minutes)
        c.close()

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "success", "mode": "bulk_sending"}

@router.post("/api/campaigns/{campaign_id}/schedule")
def post_schedule(campaign_id: int, req: BulkScheduleRequest = BulkScheduleRequest(), conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    import threading
    from datetime import datetime, timezone

    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    config = load_config(config_path())
    run_preflight(conn, config, campaign, user_id)

    db.set_campaign_status(conn, "scheduled", campaign_id, user_id)

    scheduled_dt = None
    if req.scheduled_at:
        try:
            scheduled_dt = datetime.fromisoformat(req.scheduled_at)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid scheduled_at format, use ISO datetime")

    def _run():
        if scheduled_dt:
            now = datetime.now(timezone.utc)
            if scheduled_dt.tzinfo is None:
                scheduled_dt_aware = scheduled_dt.replace(tzinfo=timezone.utc)
            else:
                scheduled_dt_aware = scheduled_dt
            delay = (scheduled_dt_aware - now).total_seconds()
            if delay > 0:
                time.sleep(delay)
        c = db.init_db(get_db_path())
        camp = c.execute("SELECT status FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if camp and camp["status"] not in ("scheduled",):
            c.close()
            return
        cfg = load_config(config_path())
        bulk_send_approved(c, campaign_id, cfg, req.delay_minutes)
        c.close()

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "success", "mode": "scheduled"}

@router.post("/api/campaigns/{campaign_id}/autopilot/start")
def post_autopilot_start(campaign_id: int, req: AutopilotStartRequest = AutopilotStartRequest(), conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    config = load_config(config_path())
    run_preflight(conn, config, campaign, user_id)

    if req.days is not None:
        config.sending.days = req.days
    config.sending.start_time = req.start_time
    config.sending.end_time = req.end_time
    config.sending.daily_cap = req.daily_cap
    config.sending.delay_minutes = req.delay_minutes
    save_config(config, config_path())

    if req.scheduled_at:
        db.set_campaign_status(conn, "scheduled", campaign_id, user_id)
        db.set_setting(conn, f"campaign_{campaign_id}_autopilot_start_at", req.scheduled_at, user_id)
    else:
        db.set_campaign_status(conn, "active", campaign_id, user_id)

    start_background_autopilot(get_db_path(), config_path())
    return {"status": "success", "mode": "autopilot"}

@router.post("/api/campaigns/{campaign_id}/pause")
def post_pause(campaign_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.set_campaign_status(conn, "paused", campaign_id, user_id)
    return {"status": "success"}

@router.post("/api/campaigns/{campaign_id}/resume")
def post_resume(campaign_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # If it was scheduled before, keep scheduled; else autopilot/sending
    prev_status = str(campaign["status"])
    new_status = "sending" if prev_status == "paused" else prev_status
    db.set_campaign_status(conn, new_status, campaign_id, user_id)
    return {"status": "success", "mode": new_status}

@router.post("/api/campaigns/{campaign_id}/stop")
def post_stop(campaign_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    campaign = db.get_campaign(conn, campaign_id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.set_campaign_status(conn, "stopped", campaign_id, user_id)
    return {"status": "success"}


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

