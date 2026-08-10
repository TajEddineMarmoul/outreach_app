from __future__ import annotations

import hmac
import logging
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=True)

APP_ACCESS_TOKEN = os.getenv("APP_ACCESS_TOKEN", "")
APP_USER_ID = os.getenv("APP_USER_ID", "")
IS_PRODUCTION = os.getenv("APP_ENV", "").strip().lower() == "production"


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials

    # A private, server-to-server token keeps the zero-cost single-user
    # deployment independent from a third-party production auth domain.
    if APP_ACCESS_TOKEN:
        if not hmac.compare_digest(token, APP_ACCESS_TOKEN):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
            )
        if not APP_USER_ID:
            logger.error("APP_USER_ID is missing while APP_ACCESS_TOKEN is configured")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Application authentication is not configured",
            )
        return APP_USER_ID

    # Development/testing fallback (never accepted in production).
    if not IS_PRODUCTION and token.startswith("mock_"):
        return token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
    )
