from __future__ import annotations

import os
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=True)

CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL")

# PyJWKClient caches keys internally and handles fetching automatically
jwks_client = PyJWKClient(CLERK_JWKS_URL) if CLERK_JWKS_URL else None

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    
    # Development/testing fallback if no JWKS URL is configured
    if not CLERK_JWKS_URL:
        if token.startswith("mock_"):
            return token
        try:
            # Decode without verification to extract 'sub' for local testing
            payload = jwt.decode(token, options={"verify_signature": False})
            sub = payload.get("sub")
            if sub:
                return str(sub)
        except Exception:
            pass
        # Fallback to returning the token itself as the user_id (for simple tests/curls)
        return token

    try:
        assert jwks_client is not None
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False}
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is missing user ID (sub claim)"
            )
        return str(user_id)
    except jwt.PyJWTError as e:
        logger.error(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}"
        )
