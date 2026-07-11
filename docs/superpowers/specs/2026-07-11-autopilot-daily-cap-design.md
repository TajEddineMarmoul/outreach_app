# Autopilot Campaign-Level Daily Cap

## Overview

Add a campaign-level daily sending limit to the autopilot mode. Tracks total emails sent per day across all senders in the campaign, and stops sending for the day when the cap is reached (or when all senders hit their individual caps, whichever comes first).

## Schema

**Campaign model** — new column:

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `autopilot_daily_cap` | Integer | Yes | NULL | Max emails per day for this campaign in autopilot mode. NULL = unlimited. |

One Alembic migration, reversible.

## How It Works

### Counting

New helper in `services.py`:

```
campaign_sent_today(session, campaign_id) -> int
```

Queries `SendLog` for this `campaign_id` where `status IN ('sent', 'test_sent')` and `sent_at >= UTC midnight today`.

### Job Creation (`create_send_jobs_for_next_batch`)

After resolving eligible senders, apply the campaign cap as an additional constraint:

```
if campaign.autopilot_daily_cap is not None:
    sent_today = campaign_sent_today(session, campaign.id)
    remaining_campaign = campaign.autopilot_daily_cap - sent_today
    if remaining_campaign <= 0:
        return {reason_code: "campaign_daily_cap_reached", ...}
    recipients = recipients[:min(len(recipients), remaining_campaign)]
```

If `campaign_daily_cap_reached` is returned, `enqueue_due_campaign_batches` treats it the same as `daily_caps_reached` — calls `next_autopilot_run(force_next_day=True)` to schedule the next eligible day.

### Interaction With Sender Caps

- Each sender runs up to their individual `daily_cap` (existing behavior)
- The campaign cap is a second ceiling — stop for the day when EITHER the campaign cap OR all sender caps are hit
- Example: campaign cap = 15, 2 senders with caps 10 each → max 15/day total
- Example: campaign cap = 25, 2 senders with caps 10 each → max 20/day (sender caps are bottleneck)

### No DB Index Needed

The hot path (`enqueue_due_campaign_batches`) filters by `status` and `scheduled_at`, not by the cap column. The cap is checked inside `create_send_jobs_for_next_batch` which already loads the campaign row. Existing indexes are sufficient.

## API

### POST /api/campaigns/{id}/autopilot/start

`AutopilotRequest` adds:
```python
daily_cap: int | None = Field(default=None, ge=1)
```

Stored to `campaign.autopilot_daily_cap`.

### GET /api/campaigns/{id}/send-progress

Response adds:
```python
"campaign_daily_cap": campaign.autopilot_daily_cap,
"campaign_sent_today": campaign_sent_today(session, campaign.id),
```

## UI

### ScheduleDialog.tsx (Autopilot tab)

New field after "Delay between batches":

```
Emails per day (optional)
[      number input       ]
Leave empty for unlimited
```

### ProgressSection.tsx

When `campaign_daily_cap` is set, show a campaign-level budget row above the per-sender breakdown:

```
Campaign daily budget:  12 / 20 used  ████████░░░░
```

Hidden when cap is NULL.

## Edge Cases

| Case | Behavior |
|------|----------|
| Cap = NULL | Existing behavior, unlimited at campaign level |
| Cap changed mid-day | Next batch reads the value from the column — takes effect immediately |
| Campaign cap < sender cap sum | Campaign cap is the bottleneck, stops earlier |
| Campaign cap > sender cap sum | Sender caps are the bottleneck, natural stop |
| All senders hit cap before campaign cap | Existing behavior — schedules next day |
| Campaign cap hit, senders still have room | New `campaign_daily_cap_reached` reason → schedules next day via autopilot |
| Resume mid-day | `campaign_sent_today` already counts earlier sends, cap applies correctly |
| Multiple start/stop cycles | Value persists in column until changed via autopilot start |
