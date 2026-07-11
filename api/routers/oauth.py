from __future__ import annotations

import logging
import os
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.gmail_sender import SCOPES
from src.platform.db import get_session
from src.platform.gmail import oauth_email_for_credentials
from src.platform.oauth import flow_from_state, load_fresh_oauth_state
from src.platform.security import encrypt_text
from src.platform.services import mark_oauth_state_used, upsert_connected_sender


router = APIRouter(tags=["oauth"])
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def _redirect_error(message: str) -> RedirectResponse:
    return RedirectResponse(url=f"{FRONTEND_URL}/senders?oauth=error&message={quote(message)}")


@router.get("/api/oauth/callback")
def oauth_callback_get(
    code: str,
    state: str | None = None,
    session: Session = Depends(get_session),
):
    oauth_state = load_fresh_oauth_state(session, state)
    if not oauth_state:
        return _redirect_error("oauth_state_expired")

    try:
        flow = flow_from_state(oauth_state)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        email = oauth_email_for_credentials(credentials)
        sender = upsert_connected_sender(
            session,
            user_id=oauth_state.user_id,
            group_id=oauth_state.group_id,
            email=email,
            display_name="",
            encrypted_credentials=encrypt_text(credentials.to_json()),
            scopes=credentials.scopes or SCOPES,
        )
        mark_oauth_state_used(oauth_state)
        session.commit()
    except FileNotFoundError:
        session.rollback()
        return _redirect_error("credentials_missing")
    except Exception:
        session.rollback()
        logging.getLogger("outreach.oauth").exception("Gmail OAuth callback failed")
        return _redirect_error("oauth_exchange_failed")

    return RedirectResponse(
        url=(
            f"{FRONTEND_URL}/senders?oauth=success"
            f"&group_id={oauth_state.group_id}&sender_id={sender.id}"
        )
    )
