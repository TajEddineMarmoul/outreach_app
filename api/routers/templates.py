from __future__ import annotations

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from fastapi import APIRouter, Depends

from api.deps import db, get_db, get_current_user_id
from api.schemas import TemplateCreate

router = APIRouter()

@router.get("/api/templates")
def get_templates(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return db.get_templates(conn, user_id)

@router.post("/api/templates")
def create_template(req: TemplateCreate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    db.create_template(conn, user_id, req.title, req.subject, req.body)
    return {"status": "success"}

@router.delete("/api/templates/{template_id}")
def delete_template(template_id: int, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    db.delete_template(conn, template_id, user_id)
    return {"status": "success"}


# ----------------------------------------------------
# 4. Recipients Endpoints
# ----------------------------------------------------

