from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import db


def dashboard_metrics(conn, config, now=None) -> dict[str, object]:
    from .safety import effective_daily_cap, next_send_time, sent_today_local

    counts = db.count_contacts_by_status(conn)
    sent_today = sent_today_local(conn, config, now=now)
    cap = effective_daily_cap(conn, config, now=now)
    remaining = max(cap - sent_today, 0)
    return {
        **counts,
        "sent_today": sent_today,
        "remaining_today": remaining,
        "daily_cap_effective": cap,
        "next_scheduled_send_time": next_send_time(config, now=now),
        "autopilot_status": db.get_campaign_status(conn),
    }


def send_log_dataframe(conn, user_id: str = "default_user", campaign_id: int | None = None) -> pd.DataFrame:
    rows = [dict(row) for row in db.send_log_rows(conn, user_id=user_id, campaign_id=campaign_id)]
    return pd.DataFrame(rows)


def export_send_log(conn, path: str | Path, user_id: str = "default_user", campaign_id: int | None = None) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    send_log_dataframe(conn, user_id=user_id, campaign_id=campaign_id).to_csv(output, index=False)
    return output
