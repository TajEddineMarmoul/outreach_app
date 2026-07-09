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

def _derive_jwks_url() -> str | None:
    pk = os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "")
    if pk and pk.startswith("pk_test_"):
        import base64
        try:
            encoded = pk[len("pk_test_"):]
            decoded = base64.b64decode(encoded).decode("utf-8")
            return f"https://{decoded}/.well-known/jwks.json"
        except Exception:
            pass
    return None

if not CLERK_JWKS_URL:
    CLERK_JWKS_URL = _derive_jwks_url()

jwks_client = PyJWKClient(CLERK_JWKS_URL) if CLERK_JWKS_URL else None

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    
    # Production JWT verification via Clerk JWKS
    if jwks_client:
        try:
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

    # Development/testing fallback (no JWKS URL configured)
    if token.startswith("mock_"):
        return token
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        sub = payload.get("sub")
        if sub:
            return str(sub)
    except Exception:
        pass
    return token
