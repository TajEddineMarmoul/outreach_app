from __future__ import annotations

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from fastapi import APIRouter, Depends

from api.deps import db, get_db
from api.schemas import TemplateCreate

router = APIRouter()

@router.get("/api/templates")
def get_templates(conn=Depends(get_db)):
    return db.get_templates(conn)

@router.post("/api/templates")
def create_template(req: TemplateCreate, conn=Depends(get_db)):
    db.create_template(conn, req.title, req.subject, req.body)
    return {"status": "success"}

@router.delete("/api/templates/{template_id}")
def delete_template(template_id: int, conn=Depends(get_db)):
    db.delete_template(conn, template_id)
    return {"status": "success"}


# ----------------------------------------------------
# 4. Recipients Endpoints
# ----------------------------------------------------

