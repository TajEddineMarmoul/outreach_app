# Outreach App

FastAPI and Next.js outreach application with PostgreSQL-backed sender groups,
campaigns, contacts, OAuth credentials, delivery jobs, and immutable send logs.

## Runtime architecture

The application runs as three independent processes:

- **API:** validates requests and persists campaign commands and queued jobs.
- **Delivery worker:** schedules batches, claims jobs, sends Gmail messages, and
  recovers interrupted jobs.
- **Frontend:** manages campaigns through the API and has no ownership of
  background delivery.

Closing or refreshing the browser does not stop sending. The API does not launch
delivery threads. PostgreSQL is the durable handoff between the API and worker.

## Configuration

Copy `.env.example` to `.env` and configure at least:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
APP_ENCRYPTION_KEY=YOUR_FERNET_KEY
BACKEND_URL=http://127.0.0.1:8000
FRONTEND_URL=http://localhost:3000
```

OAuth credentials for each sender are encrypted and stored in PostgreSQL. Token
JSON files are not used.

## Local startup

On Windows, launch all required processes with:

```bat
run_servers.bat
```

On Linux or macOS:

```bash
./run_servers.sh
```

They start:

```text
API:      python -m uvicorn api.main:app --port 8000 --reload
Worker:   python -m src.platform.worker
Frontend: npm run dev
```

Do not run multiple development launchers against the same local environment.

## Free production deployment

Production uses services with free tiers and does not depend on GCP billing:

- **Frontend:** Vercel project `outreach-web`.
- **API:** Vercel Python function exposed by `server.py` in project
  `outreach-api`.
- **Database and scheduler:** Supabase Postgres. A `pg_cron` job calls
  `/internal/worker/tick` once per minute through `pg_net`; the endpoint claims
  a bounded number of durable delivery jobs on each invocation.

Both Vercel projects are connected to `main`, so pushing a verified commit is
the production deployment mechanism. The legacy GCP workflow is manual-only.

The hosted frontend uses private single-user authentication because an owned
custom domain is not available. Keep these server-only values in Vercel and
never prefix them with `NEXT_PUBLIC_`:

```dotenv
# API project
APP_ACCESS_TOKEN=long-random-api-token
APP_USER_ID=the-existing-database-user-id

# Frontend project
APP_ACCESS_TOKEN=the-same-long-random-api-token
APP_SESSION_TOKEN=a-different-long-random-session-token
APP_LOGIN_PASSWORD=a-private-workspace-password
BACKEND_URL=https://outreach-api-virid.vercel.app
```

The browser receives only an HttpOnly session cookie. The Next.js backend proxy
adds `APP_ACCESS_TOKEN` to API calls server-side.

## Delivery behavior

A campaign selects a sender group. Each batch assigns one eligible recipient to
each eligible connected sender. After the complete batch finishes, the worker
waits the configured delay before creating the next batch.

Senders at their daily cap or in a temporary error cooldown are skipped. If all
senders reach their cap, Send now pauses while Autopilot remains active and
schedules the next eligible day.

## Tests

Run the delivery-focused suite with:

```bash
python -m pytest tests/test_application_rewrite.py tests/test_gmail_sender.py tests/test_scheduler.py -q
```
