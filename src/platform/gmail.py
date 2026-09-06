from __future__ import annotations

import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from src.gmail_sender import get_connected_email
from src.platform.models import Sender
from src.platform.security import decrypt_text, encrypt_text


def credentials_from_sender(session: Session, sender: Sender) -> Credentials:
    if not sender.encrypted_oauth_credentials:
        raise RuntimeError("Sender does not have stored OAuth credentials.")

    payload = json.loads(decrypt_text(sender.encrypted_oauth_credentials))
    # A sender's refresh token can only retain the scopes it was originally
    # granted.  Do not substitute the application's *current* scope list
    # here: when a new permission (such as gmail.readonly for reply tracking)
    # is introduced, doing so turns a normal refresh of an older send-only
    # token into Google's `invalid_scope` error.  New connections persist the
    # expanded scope list on the sender; older connections continue to send
    # and are clearly marked as needing reconnection for tracking.
    granted_scopes = list(sender.scopes or [])
    creds = Credentials.from_authorized_user_info(payload, granted_scopes or None)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        sender.encrypted_oauth_credentials = encrypt_text(creds.to_json())
        session.flush()
    if not creds.valid:
        raise RuntimeError("Sender OAuth credentials are not valid. Reconnect this sender.")
    return creds


def gmail_service_for_sender(session: Session, sender: Sender):
    return build("gmail", "v1", credentials=credentials_from_sender(session, sender))


def oauth_email_for_credentials(creds: Credentials) -> str:
    return get_connected_email(creds).strip().lower()
