# Polls & Decisions

Polls give eligible members a ballot and give administrators and executives a live
Participation pulse. Open, Upcoming, Closed, and organizer draft views live at
`/dashboard/polls`.

## Creating and running a poll

1. Choose **Create poll**, then enter a title, question, optional context, and two
   or more distinct choices. Choose one answer or multiple answers and set the
   selection limit. The industrial-action template starts with:

   > Do you support that UTAG-UG embarks on an indefinite industrial action which
   > will only be called off upon full payment of both Promotion Arrears and BRA?

   - YES, I support the industrial action
   - NO, I do not support the industrial action

2. Select all active members, colleges, schools, departments, roles, chat groups,
   or individual members. Matching any selected audience is sufficient; a member
   matching several audiences counts once. Preview the eligible-member count.
3. Start immediately or choose a future opening time and a required deadline.
   All displayed schedules use **Africa/Accra (GMT)**; API timestamps include a
   timezone and are stored in UTC. Choose privacy, member result visibility, and
   whether submitted answers can change.
4. Review the ballot preview and publish. Drafts can be edited. Publication
   freezes the audience and ballot configuration.

Members see only polls they are eligible for. Management permission does not
make an organizer eligible to vote. Opening sends an inbox invitation; closure
sends an inbox link to the poll. Organizers can confirm reminders to active
eligible members who have not voted, duplicate a poll into a fresh unscheduled
draft, extend an unclosed deadline, or close an open poll early with an audited
reason. Closed polls cannot reopen.

## Voting, privacy, and results

The defaults are **confidential**, **results after closing**, and **final votes**.
Members explicitly submit their ballot and see confirmation. A retry with the
same accepted choices succeeds without creating another ballot, including
after closure. New ballots and changed choices require an open voting window.
If vote changes are enabled, changing choices replaces the existing selections
while keeping a single ballot.

Confidential polls hide individual choices from organizer screens, exports,
audit records, and realtime events. This is confidentiality at the application
boundary, not anonymous storage: ballots remain associated with accounts for
voting integrity. Named polls disclose before submission that authorized
organizers can see individual choices. Members' own ballots remain visible to
them in either privacy mode.

Member results can be visible live, after their vote, or after closing. The API
enforces the policy. Authorized organizers can see live aggregate results.
Named-ballot access requires `polls.results`; exporting also requires
`polls.export`. Administrator and executive roles receive `polls.manage`,
`polls.results`, and `polls.export`.

Turnout is submitted ballots divided by the frozen eligible-member count.
Suspended or archived members cannot submit new votes; their accepted ballots
remain counted. Multiple-choice percentages use the number of respondents as
the denominator, so percentages across options may total more than 100%.

Results show option totals, turnout, a response timeline, time remaining,
connection status, and the latest refresh time. Realtime messages invalidate
cached results without carrying ballot choices or vote counts. Clients fetch
authoritative statistics over HTTP, resync after reconnect, and refresh every
15 seconds while disconnected. Print reports and CSV exports apply the same
privacy and result-access rules.

## API and persistence

The authenticated `/api/v1/polls` resource provides:

| Method | Path suffix | Purpose |
| --- | --- | --- |
| GET / POST | `/` | List accessible polls / create a draft |
| GET | `/audiences` | Search audience metadata |
| POST | `/audience-preview` | Resolve the distinct active electorate count |
| GET / PATCH | `/{id}` | Read a poll / edit its draft configuration |
| POST | `/{id}/publish` | Freeze the electorate and publish |
| POST | `/{id}/duplicate` | Create a new draft without votes or schedule |
| PUT | `/{id}/vote` | Submit or replace the member's permitted ballot |
| GET | `/{id}/results` | Fetch authorized statistics |
| GET / POST | `/{id}/reminders/preview`, `/{id}/reminders` | Preview / send reminders |
| POST | `/{id}/extend`, `/{id}/close` | Change a deadline / close with a reason |
| GET | `/{id}/export` | Download authorized CSV results |

Mutations use the existing session cookie and `X-CSRF-Token`. Draft edits accept
the poll's `ETag` via `If-Match`. Reminder retries can reuse an
`Idempotency-Key`. Dates in requests must include a timezone.

The polling migration is `k4p5o6l7l8s9`, following `j3c4h5a6t7e8`. Relational
tables store polls, ordered options, the frozen electorate, ballots, selections,
and deduplicated notification campaigns. PostgreSQL constraints enforce one
ballot per eligible member and prevent a selection from referencing another
poll's option. Member deletion is restricted while polling history references
that account.

Voting and organizer mutations serialize through a poll row lock. The service
checks the time after acquiring that lock: opening is inclusive and closing is
exclusive, even when lifecycle workers are delayed. Ballots, audit events,
inbox notifications, and outbox records commit atomically.

The Celery beat task `utag.polls.reconcile` runs every 15 seconds. Its lifecycle
markers and campaign constraints keep opening/closing notifications
idempotent. Reuse the existing workers, beat process, transactional outbox
relay, Redis, and authenticated WebSocket infrastructure.

## Verification and rollout

Run ordinary backend tests against their isolated SQLite fixtures. For the
locking and migration checks, explicitly point `POLLS_TEST_DATABASE_URL` at a
**disposable PostgreSQL database**. Each PostgreSQL test creates a unique schema
and drops that schema when finished; it does not drop the database. Without the
environment variable, PostgreSQL tests skip.

```sh
cd apps/api
POLLS_TEST_DATABASE_URL='postgresql+psycopg://polls_test@127.0.0.1:55473/polls_test' \
  .venv/bin/pytest tests/integration/test_polls_postgres.py --no-cov -q
```

The PostgreSQL suite checks real queued concurrent requests, identical retries,
conflicting final ballots, both vote/close orderings, a request crossing the
deadline while waiting for a lock, result privacy after a concurrent deadline
extension, rollback of ballots and outbox events,
confidential exports/events, cross-poll selection constraints, member deletion,
and migration upgrade/downgrade/re-upgrade through the existing migration
history. Use a UTF-8 test database. The test role needs permission to create
schemas and inspect its own PostgreSQL lock waits.

For the focused browser journeys, run from the repository root. Use the
installed Chrome channel when the bundled Playwright browser cache is absent:

```sh
PLAYWRIGHT_CHANNEL=chrome pnpm --filter @utag/web exec playwright test \
  e2e/polls.spec.ts --workers=1
```

The polling journeys cover organizer creation/publication and member voting at
desktop and mobile widths. The Playwright configuration starts the local web
preview; tests intercept their API fixtures rather than sending real ballots.

Before an authorized production release:

1. Apply the additive migration and authorization grants in staging, then
   deploy the API, web pages, worker, and beat configuration together.
2. Run a confidential member poll and a named multiple-choice poll; verify
   targeting, scheduled opening/closing, voting, reminders, realtime reconnect,
   CSV, and print output at desktop and mobile widths.
3. Confirm the outbox relay and beat task are healthy. A delayed worker must
   delay notifications only; the API must still enforce the deadline.
4. Take the normal backup and apply `alembic upgrade head` before activating
   the production integrations. Monitor API errors, task failures, and outbox
   delivery lag.

Downgrading the polling migration removes polling data. After real ballots
exist, preserve them with the normal backup/export policy and prefer restoring
the prior application release while retaining the additive schema. Do not run
a production downgrade merely to disable the UI.
