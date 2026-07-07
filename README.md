# Local Job Outreach Sender

A small Mailmeteor-like outreach MVP for a local job-search campaign. It imports CSV or Google Sheets leads, renders personalized emails, requires preview and approval, attaches a PDF CV, sends individual Gmail API messages slowly, logs every attempt, and resumes without resending already-attempted contacts.

This is designed for targeted professional job-search outreach, not bulk spam. It does not rotate mailboxes, spoof warmup, scrape contacts, hide sends, or bypass spam filters.

## Features

- Campaign-centered UI: open a campaign, write the email, select recipients, preview, test, and start autopilot from one page.
- CSV import for Apollo/Boomerang/AmpleLeads-style exports.
- Google Sheets recipient import for public/published sheets, with OAuth support for private sheets.
- Required CSV fields: `Email`, `First Name`, `Company Name`.
- Email normalization, missing-email skipping, and SQLite-level email dedupe.
- Keyword extraction into `keyword_1`, `keyword_2`, `keyword_3`.
- Jinja2 subject/body/fallback template editing.
- Preview-first workflow with stored preview snapshots.
- Manual approval before any real send.
- PDF CV upload and attachment validation.
- Guided Gmail setup wizard for local Google OAuth Desktop credentials.
- Gmail OAuth flow with local token storage, no Gmail password or app password.
- Safe multi-sender support: connect multiple Gmail accounts, then manually choose one sender per campaign. The app never rotates senders automatically.
- Individual sends only, never BCC.
- Daily cap, warmup ramp, send delay, allowed days/time window.
- Pause/resume/stop campaign status.
- Do-not-contact list with manual and CSV import.
- Manual statuses for replied, bounced, failed, sent, and DNC.
- Send log export.
- Crash-safe send attempts: a contact with an `attempting` or `sent` log is blocked from another send.

## Setup

1. Install dependencies.

```bash
cd outreach_app
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

2. Configure environment and sending settings.

```bash
cp .env.example .env
```

Edit `.env` if needed. Defaults are:

```bash
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
OUTREACH_DB_PATH=data/outreach.db
OUTREACH_CONFIG_PATH=config.yaml
```

Edit `config.yaml` for timezone, sending days, daily cap, delay, and attachment path.

3. Run the Streamlit app.

```bash
.venv/bin/streamlit run app.py
```

4. Connect Gmail from the campaign composer.
   - Open `Campaigns`.
   - Open or create a campaign.
   - In the `From` row, click `Connect Gmail`.
   - If `credentials.json` is already present, the app opens Google login in your browser.
   - If it is missing, the app opens the Gmail setup wizard.

5. Complete the Gmail setup wizard if prompted.
   - Open Google Cloud Console.
   - Enable the Gmail API and Google Sheets API.
   - Create an OAuth Client ID.
   - Application type must be `Desktop app`.
   - Recommended: download the JSON file and upload it through the wizard.
   - Alternative: paste both Client ID and Client Secret into the wizard.
   - Client ID alone is not enough.
   - The wizard saves the file as `credentials.json` automatically.
   - Click `Connect Gmail`, log in with Google, and allow access.

6. Use the campaign workflow.
   - Write the subject and body in the campaign composer.
   - Attach your PDF CV.
   - Click `Select recipients` and choose Google Sheets, CSV, contact list, or copy/paste.
   - Review detected columns and mapped fields.
   - Click `Show preview` and inspect generated emails.
   - Send one test email to yourself.
   - Approve selected recipients.
   - Start autopilot.
   - Pause/resume/stop as needed.
   - Export logs from the campaign activity area.

Use `Connect Gmail` in the campaign composer to open the browser OAuth flow. The first connected Gmail sender stores `token.json` locally. Additional manually connected senders use separate files under `tokens/`. Google Sheets OAuth reuses the same `credentials.json` and stores `sheets_token.json`.

## CLI

The same backend is available from `python app.py`:

```bash
.venv/bin/python app.py import-csv leads.csv
.venv/bin/python app.py preview --limit 5
.venv/bin/python app.py approve --limit 20
.venv/bin/python app.py send-once --limit 1
.venv/bin/python app.py run-autopilot
.venv/bin/python app.py pause
.venv/bin/python app.py resume
.venv/bin/python app.py status
.venv/bin/python app.py export-log data/logs/send_log.csv
.venv/bin/python app.py dnc add email@example.com
.venv/bin/python app.py dnc import dnc.csv
```

## Safety Rules

The app blocks sends when:

- Recipient email is missing.
- Recipient is on do-not-contact.
- Contact is not approved.
- Contact is already sent, replied, bounced, failed, or DNC.
- Preview was not generated and stored.
- A prior `attempting` or `sent` log exists for that contact.
- Attachment is enabled but missing or not a PDF.
- Current time is outside allowed days/hours.
- Daily cap or warmup cap is reached.
- Delay between emails has not elapsed.
- Consecutive errors or bounce-rate thresholds are exceeded.
- Gmail returns rate-limit, quota, or suspicious-activity style errors.

Warmup uses real outreach only:

- Day 1: 5 emails.
- Day 2: 10 emails.
- Day 3: 15 emails.
- Day 4: 20 emails.
- Day 5+: 30 emails/day max.

The effective cap is the lowest of configured `daily_cap`, warmup cap, and `max_daily_cap_allowed_without_manual_override`.

## CSV Fields

Supported columns include:

- `First Name`
- `Last Name`
- `Company Name`
- `Company Website`
- `Email`
- `Full Name`
- `LinkedIn`
- `Title`
- `Industry`
- `Keywords`
- `Country`

Extra CSV columns are ignored. The long `Keywords` field is split on commas and the first three trimmed values are saved as `keyword_1`, `keyword_2`, and `keyword_3`.

## Tests

```bash
cd outreach_app
.venv/bin/python -m pytest -q
```

Current tests cover import, duplicate handling, missing email handling, keyword extraction, template rendering, fallback rendering, do-not-contact blocking, already-sent blocking, daily cap enforcement, time window enforcement, missing attachment blocking, and crash-resume duplicate prevention.

## Future SaaS mode

A true Mailmeteor-style public login without `credentials.json` would require deploying a hosted backend with its own Google OAuth app and redirect URI. That is future work, not part of the local MVP.

For this local app, use a Google OAuth Client ID with application type `Desktop app`. Do not use a `Web application` OAuth client for local Streamlit login. Web OAuth clients are only appropriate for a future hosted SaaS mode with a backend, redirect URI, and secure token storage.
