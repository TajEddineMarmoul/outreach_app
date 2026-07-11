from __future__ import annotations

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import db, config_path, get_db
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

@app.on_event("startup")
def on_startup():
    conn = db.init_db()
    conn.close()
    upgrade_database()

from api.routers import campaign_delivery, campaigns, contacts, oauth, sender_groups, templates, settings

app.include_router(sender_groups.router)
app.include_router(sender_groups.senders_router)
app.include_router(campaign_delivery.router)
app.include_router(campaigns.router)
app.include_router(contacts.router)
app.include_router(templates.router)
app.include_router(settings.router)
app.include_router(oauth.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
