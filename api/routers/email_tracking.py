from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import get_current_user_id
from src.platform.db import get_session
from src.platform.email_tracking import (
    record_click,
    record_open,
    tracking_is_configured,
)
from src.platform.models import Campaign


router = APIRouter(tags=["email-engagement"])

TRANSPARENT_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9"
    b"\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, max-age=0, private",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-Robots-Tag": "noindex, nofollow",
}


class EngagementTrackingUpdate(BaseModel):
    enabled: bool


def _campaign(session: Session, campaign_id: int, user_id: str) -> Campaign:
    campaign = session.scalar(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id)
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.get("/api/campaigns/{campaign_id}/engagement-tracking")
def get_engagement_tracking(
    campaign_id: int,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    campaign = _campaign(session, campaign_id, user_id)
    return {
        "enabled": campaign.engagement_tracking_enabled,
        "configured": tracking_is_configured(),
    }


@router.patch("/api/campaigns/{campaign_id}/engagement-tracking")
def patch_engagement_tracking(
    campaign_id: int,
    payload: EngagementTrackingUpdate,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
):
    campaign = _campaign(session, campaign_id, user_id)
    if campaign.status in {"sending", "scheduled", "autopilot"}:
        raise HTTPException(status_code=409, detail="End or pause the campaign before changing engagement tracking")
    campaign.engagement_tracking_enabled = payload.enabled
    session.commit()
    return {"enabled": campaign.engagement_tracking_enabled, "configured": tracking_is_configured()}


@router.get("/api/track/o/{token}.gif", include_in_schema=False)
def track_open(token: str, session: Session = Depends(get_session)):
    # A missing or expired token is still a valid transparent image response.
    # It avoids turning a forwarded old email into a broken-image experience.
    record_open(session, token)
    return Response(TRANSPARENT_GIF, media_type="image/gif", headers=NO_CACHE_HEADERS)


@router.get("/api/track/c/{token}", include_in_schema=False)
def track_click(token: str, session: Session = Depends(get_session)):
    destination_url = record_click(session, token)
    if not destination_url:
        raise HTTPException(status_code=404, detail="Tracked link not found")
    response = RedirectResponse(destination_url, status_code=302)
    response.headers.update(NO_CACHE_HEADERS)
    return response
