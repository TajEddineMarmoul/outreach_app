from __future__ import annotations

import json
import os
import base64
import secrets
from urllib.parse import quote
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from api.deps import db, get_db, get_current_user_id, get_db_path, config_path
from api.schemas import SettingsUpdate
from src.models import load_config
from src.gmail_sender import credentials_file_path, SCOPES
from google_auth_oauthlib.flow import Flow
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


class CredentialsContent(BaseModel):
    content: str


class OAuthCode(BaseModel):
    code: str
    state: str | None = None


FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
OAUTH_STATE_SETTING = "oauth_pkce_states"
OAUTH_STATE_TTL = timedelta(minutes=15)


def _encode_oauth_state(user_id: str, nonce: str) -> str:
    payload = json.dumps({"user_id": user_id, "nonce": nonce}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_oauth_state(state: str | None) -> tuple[str, str | None]:
    if not state:
        return "default_user", None
    try:
        padded = state + ("=" * (-len(state) % 4))
        decoded = base64.urlsafe_b64decode(padded.encode()).decode()
        payload = json.loads(decoded)
        user_id = str(payload.get("user_id") or "default_user")
        nonce = payload.get("nonce")
        return user_id, str(nonce) if nonce else None
    except Exception:
        # Backward compatibility for old state values that only contained user_id.
        try:
            return base64.urlsafe_b64decode(state.encode()).decode(), None
        except Exception:
            return "default_user", None


def _oauth_state_is_fresh(created_at: str | None) -> bool:
    if not created_at:
        return False
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return False
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - created <= OAUTH_STATE_TTL


def _load_pending_oauth_states(conn, user_id: str) -> dict[str, dict[str, str]]:
    states = db.get_setting(conn, OAUTH_STATE_SETTING, {}, user_id)
    if not isinstance(states, dict):
        return {}
    return {
        str(nonce): value
        for nonce, value in states.items()
        if isinstance(value, dict) and _oauth_state_is_fresh(value.get("created_at"))
    }


def _handle_db_oauth_callback(code: str, state: str | None, *, redirect: bool):
    if not state:
        return None
    try:
        from src.platform.db import SessionLocal
        from src.platform.gmail import oauth_email_for_credentials
        from src.platform.oauth import flow_from_state, load_fresh_oauth_state
        from src.platform.security import encrypt_text
        from src.platform.services import mark_oauth_state_used, upsert_connected_sender
    except Exception:
        return None

    session = SessionLocal()
    try:
        oauth_state = load_fresh_oauth_state(session, state)
        if not oauth_state:
            return None

        flow = flow_from_state(oauth_state)
        flow.fetch_token(code=code)
        creds = flow.credentials
        email = oauth_email_for_credentials(creds)
        sender = upsert_connected_sender(
            session,
            user_id=oauth_state.user_id,
            group_id=oauth_state.group_id,
            email=email,
            display_name="",
            encrypted_credentials=encrypt_text(creds.to_json()),
            scopes=creds.scopes or SCOPES,
        )
        mark_oauth_state_used(oauth_state)
        session.commit()
        if redirect:
            return RedirectResponse(
                url=(
                    f"{FRONTEND_URL}/senders?oauth=success"
                    f"&group_id={oauth_state.group_id}&sender_id={sender.id}&email={quote(email)}"
                )
            )
        return {"status": "success", "email": email, "sender_id": sender.id, "group_id": oauth_state.group_id}
    except SQLAlchemyError:
        session.rollback()
        return None
    except Exception as exc:
        session.rollback()
        if redirect:
            return RedirectResponse(url=f"{FRONTEND_URL}/senders?oauth=error&message={quote(str(exc))}")
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        session.close()

@router.get("/api/settings")
def get_settings(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    config = load_config(config_path())
    
    timezone = db.get_setting(conn, "timezone", config.timezone, user_id)
    max_daily_cap = db.get_setting(conn, "max_daily_cap", config.sending.max_daily_cap_allowed_without_manual_override, user_id)
    bounce_rate_pause_threshold = db.get_setting(conn, "bounce_rate_pause_threshold", config.sending.bounce_rate_pause_threshold, user_id)
    max_consecutive_errors = db.get_setting(conn, "max_consecutive_errors", config.sending.max_consecutive_errors, user_id)
    
    return {
        "timezone": timezone,
        "max_daily_cap": max_daily_cap,
        "bounce_rate_pause_threshold": bounce_rate_pause_threshold,
        "max_consecutive_errors": max_consecutive_errors,
        "config_path": str(config_path()),
    }

@router.patch("/api/settings")
def patch_settings(req: SettingsUpdate, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    db.set_setting(conn, "timezone", req.timezone, user_id)
    db.set_setting(conn, "max_daily_cap", req.max_daily_cap, user_id)
    db.set_setting(conn, "bounce_rate_pause_threshold", req.bounce_rate_pause_threshold, user_id)
    db.set_setting(conn, "max_consecutive_errors", req.max_consecutive_errors, user_id)
    return {"status": "success"}

@router.get("/api/oauth/status")
def get_oauth_status(user_id: str = Depends(get_current_user_id)):
    path = credentials_file_path()
    return {"credentials_json_present": path.exists()}

@router.post("/api/oauth/save-credentials-json")
def save_credentials(req: CredentialsContent, user_id: str = Depends(get_current_user_id)):
    try:
        data = json.loads(req.content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")

    client_section = data.get("web") or data.get("installed")
    if not client_section:
        raise HTTPException(status_code=400, detail="OAuth JSON must contain a 'web' or 'installed' key")

    client_id = (client_section.get("client_id") or "").strip()
    client_secret = (client_section.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Missing client_id or client_secret")

    path = credentials_file_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"status": "success", "client_type": "web" if "web" in data else "installed"}


@router.post("/api/oauth/start")
def start_oauth(conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    path = credentials_file_path()
    if not path.exists():
        raise HTTPException(status_code=400, detail="Save credentials.json first")

    redirect_uri = f"{BACKEND_URL}/api/oauth/callback"
    flow = Flow.from_client_secrets_file(str(path), SCOPES, redirect_uri=redirect_uri)
    nonce = secrets.token_urlsafe(24)
    encoded_state = _encode_oauth_state(user_id, nonce)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=encoded_state,
    )

    pending_states = _load_pending_oauth_states(conn, user_id)
    pending_states[nonce] = {
        "code_verifier": flow.code_verifier,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.set_setting(conn, OAUTH_STATE_SETTING, pending_states, user_id)

    return {"auth_url": auth_url}


@router.get("/api/oauth/callback")
def oauth_callback_get(code: str, state: str | None = None, conn=Depends(get_db)):
    from src.gmail_sender import sender_token_path_for_email, get_connected_email

    db_response = _handle_db_oauth_callback(code, state, redirect=True)
    if db_response is not None:
        return db_response

    resolved_user_id, nonce = _decode_oauth_state(state)

    path = credentials_file_path()
    if not path.exists():
        return RedirectResponse(url=f"{FRONTEND_URL}/senders?oauth=error&message=credentials_missing")

    try:
        pending_states = _load_pending_oauth_states(conn, resolved_user_id)
        pending_state = pending_states.pop(nonce, None) if nonce else None
        if not pending_state or not pending_state.get("code_verifier"):
            return RedirectResponse(url=f"{FRONTEND_URL}/senders?oauth=error&message=oauth_state_expired")
        db.set_setting(conn, OAUTH_STATE_SETTING, pending_states, resolved_user_id)

        redirect_uri = f"{BACKEND_URL}/api/oauth/callback"
        flow = Flow.from_client_secrets_file(
            str(path),
            SCOPES,
            redirect_uri=redirect_uri,
            code_verifier=pending_state["code_verifier"],
            autogenerate_code_verifier=False,
        )
        flow.fetch_token(code=code)

        creds = flow.credentials
        email = get_connected_email(creds)

        # Save token file
        token_path = sender_token_path_for_email(email, resolved_user_id)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

        # Persist sender to the database
        db.upsert_sender(
            conn,
            email=email,
            token_path=str(token_path),
            user_id=resolved_user_id,
            display_name="",
            daily_cap=10,
            status="connected",
        )
        db.set_setting(conn, "sender_email", email, resolved_user_id)

        return RedirectResponse(url=f"{FRONTEND_URL}/senders?oauth=success&email={email}")
    except Exception as e:
        import traceback; traceback.print_exc()
        return RedirectResponse(url=f"{FRONTEND_URL}/senders?oauth=error&message={str(e)}")


@router.post("/api/oauth/callback")
def oauth_callback(req: OAuthCode, conn=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    from src.gmail_sender import sender_token_path_for_email, get_connected_email

    db_response = _handle_db_oauth_callback(req.code, req.state, redirect=False)
    if db_response is not None:
        return db_response

    path = credentials_file_path()
    if not path.exists():
        raise HTTPException(status_code=400, detail="Save credentials.json first")

    resolved_user_id, nonce = _decode_oauth_state(req.state)
    if resolved_user_id == "default_user" and not nonce:
        resolved_user_id = user_id

    pending_states = _load_pending_oauth_states(conn, resolved_user_id)
    pending_state = pending_states.pop(nonce, None) if nonce else None
    if not pending_state or not pending_state.get("code_verifier"):
        raise HTTPException(status_code=400, detail="OAuth state expired. Start the OAuth flow again.")
    db.set_setting(conn, OAUTH_STATE_SETTING, pending_states, resolved_user_id)

    redirect_uri = f"{BACKEND_URL}/api/oauth/callback"
    flow = Flow.from_client_secrets_file(
        str(path),
        SCOPES,
        redirect_uri=redirect_uri,
        code_verifier=pending_state["code_verifier"],
        autogenerate_code_verifier=False,
    )
    flow.fetch_token(code=req.code)

    creds = flow.credentials
    email = get_connected_email(creds)

    token_path = sender_token_path_for_email(email, resolved_user_id)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")

    db.upsert_sender(
        conn,
        email=email,
        token_path=str(token_path),
        user_id=resolved_user_id,
        display_name="",
        daily_cap=10,
        status="connected",
    )
    db.set_setting(conn, "sender_email", email, resolved_user_id)

    return {"status": "success", "email": email}
