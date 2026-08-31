# Onboarding and contact imports

This release adds a getting-started page explaining campaigns, a fictional
sample, and optional tips on Audience, Message, and Review. Each tip can be
dismissed independently. Help lives in Menu, where users can show tips again
without leaving their current page. Welcome completion and tip preferences are
saved per user in the current browser.

Campaign audiences use one Import contacts action with paste, CSV, and Google
Sheets options. The fixed Add one person form is removed from campaign setup.
The header row must contain an email column; extra columns remain available as
message fields. Imports display a read-only preview before the user confirms.
Google Sheets links still require public access; restricted sheets can be
exported to CSV or pasted. Preview endpoints do not import or send anything.

## Verification

- Production Next.js build and TypeScript checks.
- Scoped ESLint covering all changed frontend components.
- 26 Python tests covering recipient previews, imports, and campaign workspace
  behavior with mocks or isolated SQLite databases.
- Signed-in local browser checks for welcome, independent tips, dismissal,
  restoring tips through Help, and import previews. No real emails were sent.

## Release

No database migration or environment change is required. The connected
outreach-web and outreach-api Vercel projects deploy from main. Verify both
projects use the release commit, then check the live frontend and preview API.
Local delivery remains disabled. Personal files and design mockups are excluded.
