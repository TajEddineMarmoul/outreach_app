from __future__ import annotations

import base64
import json
import os
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.platform.db import get_session
from src.platform.gmail_activity import enqueue_gmail_push_notification


router = APIRouter(tags=["gmail-events"])


class PubSubMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    data: str
    message_id: str | None = Field(default=None, alias="messageId")


class PubSubEnvelope(BaseModel):
    message: PubSubMessage
    subscription: str | None = None


@lru_cache(maxsize=32)
def _verify_push_token(token: str, audience: str) -> dict[str, Any]:
    claims = id_token.verify_oauth2_token(token, GoogleAuthRequest(), audience=audience)
    expected_service_account = os.getenv("GMAIL_PUBSUB_PUSH_SERVICE_ACCOUNT", "").strip().lower()
    token_email = str(claims.get("email") or "").strip().lower()
    if not expected_service_account:
        raise ValueError("GMAIL_PUBSUB_PUSH_SERVICE_ACCOUNT is not configured")
    if token_email != expected_service_account or claims.get("email_verified") is not True:
        raise ValueError("Unexpected Pub/Sub push identity")
    return claims


def _authenticate_push(authorization: str | None) -> None:
    audience = os.getenv("GMAIL_PUBSUB_PUSH_AUDIENCE", "").strip()
    if not audience:
        raise HTTPException(status_code=503, detail="Gmail push authentication is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Pub/Sub identity token")
    try:
        _verify_push_token(authorization.removeprefix("Bearer ").strip(), audience)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Pub/Sub identity token") from exc


def _notification_data(encoded_data: str) -> tuple[str, str]:
    try:
        decoded = base64.b64decode(encoded_data, validate=True)
        payload = json.loads(decoded.decode("utf-8"))
        email_address = str(payload["emailAddress"]).strip().lower()
        history_id = str(payload["historyId"]).strip()
        if not email_address or int(history_id) <= 0:
            raise ValueError
        return email_address, history_id
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Gmail notification payload") from exc


@router.post("/api/webhooks/gmail", status_code=204)
def gmail_push_webhook(
    envelope: PubSubEnvelope,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Response:
    """Persist a coalesced mailbox event and acknowledge Pub/Sub immediately."""
    _authenticate_push(authorization)
    email_address, history_id = _notification_data(envelope.message.data)
    enqueue_gmail_push_notification(
        session,
        email_address=email_address,
        history_id=history_id,
    )
    session.commit()
    return Response(status_code=204)
