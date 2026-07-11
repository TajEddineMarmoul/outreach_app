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

For production, run the API and `python -m src.platform.worker` as separately
supervised services using the same code, environment, and PostgreSQL database.
Do not run multiple development launchers against the same local environment.

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
