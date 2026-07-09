from __future__ import annotations

import os
import secrets
from datetime import timedelta

from google_auth_oauthlib.flow import Flow
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.gmail_sender import SCOPES, credentials_file_path
from src.platform.models import OAuthState
from src.platform.services import ensure_user, require_group
from src.platform.time import utcnow


FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
OAUTH_STATE_TTL = timedelta(minutes=15)


def callback_url() -> str:
    return f"{BACKEND_URL}/api/oauth/callback"


def create_sender_oauth_start(session: Session, *, user_id: str, group_id: int) -> str:
    ensure_user(session, user_id)
    require_group(session, user_id, group_id)

    path = credentials_file_path()
    if not path.exists():
        raise FileNotFoundError("Google OAuth client credentials JSON is missing.")

    flow = Flow.from_client_secrets_file(str(path), SCOPES, redirect_uri=callback_url())
    state = secrets.token_urlsafe(32)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account consent",
        state=state,
    )
    session.add(
        OAuthState(
            state=state,
            user_id=user_id,
            group_id=group_id,
            code_verifier=flow.code_verifier,
            expires_at=utcnow() + OAUTH_STATE_TTL,
        )
    )
    session.flush()
    return auth_url


def load_fresh_oauth_state(session: Session, state_value: str | None) -> OAuthState | None:
    if not state_value:
        return None
    state = session.scalar(select(OAuthState).where(OAuthState.state == state_value))
    if not state or state.used_at:
        return None
    expires_at = state.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=utcnow().tzinfo)
    if expires_at <= utcnow():
        return None
    return state


def flow_from_state(state: OAuthState) -> Flow:
    path = credentials_file_path()
    if not path.exists():
        raise FileNotFoundError("Google OAuth client credentials JSON is missing.")
    return Flow.from_client_secrets_file(
        str(path),
        SCOPES,
        redirect_uri=callback_url(),
        code_verifier=state.code_verifier,
        autogenerate_code_verifier=False,
    )
