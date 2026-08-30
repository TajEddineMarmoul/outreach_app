from fastapi import HTTPException, status

from src.platform.delivery_safety import delivery_block_reason, delivery_enabled


def require_delivery_enabled() -> None:
    if not delivery_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=delivery_block_reason(),
        )
