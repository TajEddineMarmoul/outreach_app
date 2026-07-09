from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.platform.db import SessionLocal
from src.platform.jobs import create_send_jobs_for_next_batch, perform_send_job
from src.platform.models import Campaign
from src.platform.time import utcnow


def enqueue_due_campaign_batches(session: Session, *, limit: int = 25) -> list[dict]:
    now = utcnow()
    campaigns = list(
        session.scalars(
            select(Campaign)
            .where(
                Campaign.status.in_(("sending", "scheduled")),
                Campaign.scheduled_at.is_not(None),
                Campaign.scheduled_at <= now,
            )
            .order_by(Campaign.scheduled_at, Campaign.id)
            .limit(limit)
        )
    )
    results: list[dict] = []
    job_ids: list[int] = []
    for campaign in campaigns:
        delay_minutes = int((campaign.send_settings or {}).get("delay_minutes", 5))
        result = create_send_jobs_for_next_batch(
            session,
            user_id=campaign.user_id,
            campaign_id=campaign.id,
            delay_minutes=delay_minutes,
            scheduled_for=now,
        )
        if result.get("created", 0) == 0 and result.get("reason") == "No approved recipients are ready":
            campaign.status = "ended"
        job_ids.extend(result.get("job_ids", []))
        results.append({"campaign_id": campaign.id, **result})
    session.commit()
    import threading
    def _run():
        for jid in job_ids:
            perform_send_job(jid)
    threading.Thread(target=_run, daemon=True).start()
    for result in results:
        result["queued"] = len(result.get("job_ids", []))
    return results


def run_scheduler_loop(poll_seconds: int = 30) -> None:
    while True:
        session = SessionLocal()
        try:
            enqueue_due_campaign_batches(session)
        finally:
            session.close()
        time.sleep(poll_seconds)


if __name__ == "__main__":
    run_scheduler_loop()
