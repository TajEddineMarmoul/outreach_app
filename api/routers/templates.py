from __future__ import annotations

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from fastapi import APIRouter, Depends, HTTPException

from api.deps import db, get_db, get_current_user_id
from api.schemas import TemplateCreate

router = APIRouter()

@router.get("/api/templates")
def get_templates(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return db.get_templates(conn, user_id)

@router.post("/api/templates")
def create_template(req: TemplateCreate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    _validate_template(req)
    template_id = db.create_template(conn, user_id, req.title, req.subject, req.body)
    conn.execute("UPDATE templates SET updated_at = ? WHERE id = ? AND user_id = ?", (db.utcnow_iso(), template_id, user_id))
    conn.commit()
    return {
        "id": template_id,
        "title": req.title,
        "subject": req.subject,
        "body": req.body,
        "status": "success",
    }


def _validate_template(req: TemplateCreate):
    if not req.title.strip() or not req.subject.strip() or not req.body.strip():
        raise HTTPException(status_code=422, detail="Name, subject, and message are required")
    if len(req.title) > 240 or len(req.subject) > 998 or len(req.body) > 500000:
        raise HTTPException(status_code=422, detail="Template exceeds the allowed length")


@router.patch("/api/templates/{template_id}")
def update_template(template_id: int, req: TemplateCreate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    _validate_template(req)
    existing = conn.execute("SELECT id FROM templates WHERE id = ? AND user_id = ?", (template_id, user_id)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    conn.execute("UPDATE templates SET title = ?, subject = ?, body = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                 (req.title.strip(), req.subject, req.body, db.utcnow_iso(), template_id, user_id))
    conn.commit()
    return {"status": "success", "id": template_id}

@router.delete("/api/templates/{template_id}")
def delete_template(template_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    db.delete_template(conn, template_id, user_id)
    return {"status": "success"}


# ----------------------------------------------------
# 4. Recipients Endpoints
# ----------------------------------------------------
