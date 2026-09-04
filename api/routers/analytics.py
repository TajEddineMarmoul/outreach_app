from datetime import timedelta
from io import StringIO
import csv

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.auth import get_current_user_id
from src.platform.db import get_session
from src.platform.models import GmailActivityEvent, SendLog
from src.platform.time import utcnow

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
SENT_STATUSES = ("sent", "success")
ATTEMPT_STATUSES = (*SENT_STATUSES, "bounced", "failed", "error")


def _window(user_id, days):
    now = utcnow()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    return start, [SendLog.user_id == user_id, SendLog.created_at >= start, SendLog.created_at <= now, SendLog.status.in_(ATTEMPT_STATUSES)]


@router.get("")
def analytics(days: int = Query(default=7, ge=1, le=30), page: int = Query(default=1, ge=1),
              session: Session = Depends(get_session), user_id: str = Depends(get_current_user_id)):
    start, filters = _window(user_id, days)
    counts = dict(session.execute(select(SendLog.status, func.count()).where(*filters).group_by(SendLog.status)).all())
    sent = sum(counts.get(status, 0) for status in SENT_STATUSES)
    undelivered = counts.get("bounced", 0)
    send_errors = counts.get("failed", 0) + counts.get("error", 0)
    total = sum(counts.values())
    response_counts = dict(
        session.execute(
            select(GmailActivityEvent.event_type, func.count(func.distinct(GmailActivityEvent.recipient_email)))
            .where(
                GmailActivityEvent.user_id == user_id,
                GmailActivityEvent.occurred_at >= start,
                GmailActivityEvent.occurred_at <= utcnow(),
                GmailActivityEvent.event_type.in_(("replied", "automated_response")),
            )
            .group_by(GmailActivityEvent.event_type)
        ).all()
    )
    # PostgreSQL date extraction must not depend on the connection timezone.
    timestamp = func.timezone("UTC", SendLog.created_at) if session.bind.dialect.name == "postgresql" else SendLog.created_at
    date = func.date(timestamp)
    daily = {str(day): count for day, count in session.execute(select(date, func.count()).where(*filters, SendLog.status.in_(SENT_STATUSES)).group_by(date))}
    series = [{"date": (start + timedelta(days=index)).date().isoformat(), "sent": daily.get((start + timedelta(days=index)).date().isoformat(), 0)} for index in range(days)]
    logs = session.scalars(select(SendLog).where(*filters).order_by(SendLog.created_at.desc(), SendLog.id.desc()).offset((page - 1) * 6).limit(6))
    return {"attempts": total, "sent": sent, "replied": response_counts.get("replied", 0),
            "automated_responses": response_counts.get("automated_response", 0),
            "undelivered": undelivered, "send_errors": send_errors,
            "failed": undelivered + send_errors, "series": series, "timezone": "UTC", "page": page,
            "items": [{"id": row.id, "email": row.recipient_email, "subject": row.subject, "created_at": row.created_at,
                       "status": row.status, "response_status": row.response_status,
                       "responded_at": row.responded_at, "error_message": row.error_message} for row in logs]}


@router.get("/export")
def export_analytics(days: int = Query(default=7, ge=1, le=30), session: Session = Depends(get_session), user_id: str = Depends(get_current_user_id)):
    _, filters = _window(user_id, days)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Recipient", "Subject", "Delivery status", "Response", "Sent at (UTC)", "Responded at (UTC)", "Details"])
    for row in session.scalars(select(SendLog).where(*filters).order_by(SendLog.created_at.desc())):
        values = [
            row.recipient_email,
            row.subject,
            row.status,
            row.response_status or "",
            row.created_at.isoformat(),
            row.responded_at.isoformat() if row.responded_at else "",
            row.error_message or "",
        ]
        writer.writerow(["'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value for value in values])
    return Response("\ufeff" + output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="delivery-last-{days}-days.csv"'})
