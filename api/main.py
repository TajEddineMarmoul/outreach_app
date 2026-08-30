from __future__ import annotations

import os
import logging
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.deps import db
from src.platform.db import SessionLocal
from src.platform.migrations import upgrade_database

app = FastAPI(title="Outreach App API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=os.getenv("CORS_ALLOW_ORIGIN_REGEX", ".*"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

def _env_flag(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@app.on_event("startup")
def on_startup():
    # A serverless deployment can start multiple instances concurrently. The
    # database is migrated explicitly during deployment instead of on every
    # cold start, avoiding migration races and unnecessary startup work.
    default = not bool(os.getenv("VERCEL"))
    if _env_flag("RUN_DATABASE_MIGRATIONS", default=default):
        conn = db.init_db()
        conn.close()
        upgrade_database()


@app.get("/health", tags=["health"])
def health():
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        logging.getLogger("outreach.health").exception("Database health check failed")
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "database": "ok"}

from api.routers import analytics, campaign_delivery, campaign_workspace, campaigns, contacts, oauth, sender_groups, templates, settings

app.include_router(sender_groups.router)
app.include_router(sender_groups.senders_router)
app.include_router(campaign_delivery.router)
app.include_router(campaign_workspace.router)
app.include_router(campaigns.router)
app.include_router(contacts.router)
app.include_router(templates.router)
app.include_router(settings.router)
app.include_router(oauth.router)
app.include_router(analytics.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
