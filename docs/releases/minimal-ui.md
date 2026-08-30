# Minimal Outreach UI

The approved campaign workspace and six surrounding pages are implemented in
the application. The generated images in `docs/ui-concepts` remain design
references; they are not the runtime UI.

## Behavior

- A labeled Menu replaces the permanent sidebar. Settings and Help live inside it.
- Campaign setup uses Audience, Message, Senders, Schedule, and Review in one
  bottom navigation bar. Optional message tools and preview open on demand.
- TrackMailBox / Gmail-compose shortcuts and attachment requirements are absent
  from the UI. Attachments remain optional; no tracking feature is introduced.
- Campaigns, Contacts, Senders, and Templates use compact lists. Search,
  pagination, contextual menus, empty states, and failures are handled explicitly.
- Contacts can be added individually or imported from CSV. The do-not-contact
  list and exports are in More. Clearing a campaign audience does not remove
  global contacts, messages, schedules, attachments, or send history.
- Templates can be edited without changing existing campaign messages.
- Analytics shows delivery attempts, sent, and failed totals over a selected
  UTC date range, with one daily chart and collapsed history. Simulated sends
  are excluded. Sent means provider acceptance, not confirmed inbox delivery.
- Settings initially shows only the default timezone; connected services and
  advanced settings are collapsed.

## Database upgrade

Apply migrations through `0012_template_updated_at` before this frontend release.
`0011_campaign_timezone` fixes each existing campaign to its current account
timezone (UTC if none exists). `0012_template_updated_at` records future template
edits; historical template dates remain unknown rather than invented.

Both changes are additive. Rolling the application back does not require dropping
these columns. Preserve the columns on rollback so newly saved settings survive.

Campaign creation also reads the generated ID before commit, while the same
pooled database connection still owns the insert transaction.

## Verification

- Production Next.js build, TypeScript, and scoped ESLint checks.
- 101 targeted Python tests covering the new APIs, ownership, migrations,
  campaign behavior, OAuth lifecycle with mocks, and delivery safety.
- Three schedule regression tests, including stale hidden start dates.
- Real PostgreSQL integration checks in a separate schema copied from production
  structure without any production data. Test sequences are separate.
- Authenticated browser checks against the real local frontend and API, including
  campaign creation, recipient entry, message saving and preview, schedule modes,
  review gating, navigation, template edits, sender limit changes, and timezone
  saving. Settings keeps optional sections collapsed. Desktop checks use a
  1366 × 700 viewport; mobile checks use 390 × 844 with no page-wide overflow.
  Analytics and the menu fit the desktop height without scrolling by default.

No real emails are sent during local QA. Gmail transmission is tested with the
existing fake-provider delivery suite; connecting a real mailbox is not required
for these layout changes.

The production upgrade path from `0010_multi_attachments` to `0012` is verified.
An unrelated historical migration issue still prevents creating a completely
empty PostgreSQL database through the full migration chain: `0001` creates a
table that `0005` also tries to add. This release does not alter those historical
migrations and does not rely on a fresh database install.

## Release

Production is deployed from `main` by the connected `outreach-web` and
`outreach-api` Vercel projects. Publish only the verified application files;
personal notes, local test helpers, test schema configuration, and credentials
must remain outside the release. Verify both deployments and authenticated page
loads afterward. Local sending stays disabled when reconnecting to live data.
