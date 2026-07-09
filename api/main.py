from __future__ import annotations

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import db, get_db_path, config_path, get_db
from src.scheduler import start_background_autopilot

app = FastAPI(title="Outreach App API", version="1.0.0")

_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://outreach-web-mu.vercel.app",
]
_origins = os.getenv("CORS_ORIGINS", ",".join(_default_origins)).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_scheduler = None

@app.on_event("startup")
def on_startup():
    global _scheduler
    conn = db.init_db(get_db_path())
    conn.close()
    _scheduler = start_background_autopilot(get_db_path(), config_path())

@app.on_event("shutdown")
def on_shutdown():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()

from api.routers import campaigns, senders, contacts, templates, settings

app.include_router(campaigns.router)
app.include_router(senders.router)
app.include_router(contacts.router)
app.include_router(templates.router)
app.include_router(settings.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
