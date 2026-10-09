# The admin portal

How to run the admin portal at `/admin` ([ADR 0015](adr/0015-admin-portal.md)). The design
reference is `docs/design/reference-admin.html`.

## Add an admin owner

Owners are never stored in the database. They come only from the server setting
`ADMIN_OWNER_EMAILS`.

1. The person signs in to the app once, with an email code or Google, so an account exists
   for their address.
2. In the Render dashboard, add their address to `ADMIN_OWNER_EMAILS` on the API service.
   It's a comma-separated list. Save; Render restarts the API. Don't put the address in the
   repository.
3. They open `/admin`. The first time, the portal asks them to set up two-step login:
   - scan the code with an authenticator app (any TOTP app works);
   - enter one code to confirm;
   - save the 10 recovery codes it shows once.
4. From then on, `/admin` asks for a code from the app (or a recovery code) and opens a
   separate admin session. It ends after 30 idle minutes and after 12 hours at most.

To remove an owner, take their address out of `ADMIN_OWNER_EMAILS`. Their admin access ends
on their next request.

**Other roles** (admin, moderator, read-only) are given by an owner on **Team and audit**,
to people who already have an account. Each grant takes a reason and is audited. What each
role may do is the table on that page; the server checks it on every request.

If someone loses their authenticator, they use a recovery code. If they've lost those too,
an owner removes their role and grants it again, which makes them set up two-step login
again. For an owner, remove and re-add their address in `ADMIN_OWNER_EMAILS` after deleting
their `admin_accounts` row; that last step needs database access.

## Environment variables

Set these on the **API** service in Render. Secrets go only in the dashboard, never in the
repository. Every one is described in `backend/.env.example`.

| Variable | Default | What it does |
| --- | --- | --- |
| `ADMIN_OWNER_EMAILS` | empty | Comma-separated owner addresses. Empty: nobody can use the portal. |
| `ADMIN_SESSION_IDLE_MINUTES` | 30 | The admin session ends after this many idle minutes (5 to 60). |
| `ADMIN_SESSION_MAX_HOURS` | 12 | …and after this many hours, whatever happens (1 to 24). |
| `ADMIN_TWO_STEP_ATTEMPTS` | 5 | Two-step code tries per admin per 15 minutes. |
| `ADMIN_REQUESTS_PER_MINUTE` | 30 | Requests per IP per minute to `/api/v1/admin`. |
| `ADMIN_API_TOKEN` | empty | Machine token for the operator endpoints (storage, jobs). Secret. |
| `JOBS_TICK_TOKEN` | empty | The scheduler's token for `POST /api/v1/admin/jobs/tick`. Secret. |
| `AI_PROBES_PER_DAY` | 5 | "Test the AI providers" runs per person per day. |
| `MODERATOR_EMAIL` | empty | Where the hourly "new reports" email goes. |
| `MODERATOR_EMAILS` | empty | Accounts that may use the older `/moderation` page. |
| `TERMS_VERSION` | see `.env.example` | The current terms; the Data page's consent numbers use it. |
| `WEB_APP_URL` | empty | Links in emails (invites, data downloads, appeals). |

The web app needs no admin-specific variables: it calls the API through its own `/api/v1/*`.

Nothing else is configured by environment. Signup mode, invite codes, email domains, feature
switches, limits, content rules, AI provider switches and banners are all set in the portal.
They are stored in the database and applied within 60 seconds.

## Run the performance seed

`backend/scripts/seed_perf.py` fills a **local or throwaway** database with 100,000 fake
people (`perf-<n>@example.com`). It then times the admin Users queries and the Overview with
`EXPLAIN ANALYZE`, and fails if any takes 200 ms or more. It refuses to run unless
`DATABASE_URL` points at localhost, so it can never touch staging or production.

- **In CI:** the **Admin performance** workflow runs it on a throwaway database for pull
  requests that touch the admin code, or by hand from Actions → Admin performance → Run
  workflow. Its log prints each query's median time.
- **In a Codespace,** with the stack running (`docker compose up --build --detach --wait`):

  ```sh
  docker compose run --rm migrate alembic upgrade head
  docker compose run --rm api python -m scripts.seed_perf
  ```

  Run it on a fresh database (`docker compose down -v` first): the people it adds stay
  until the volume is deleted.

## Pages and permissions

| Page | Who sees it | Notes |
| --- | --- | --- |
| Overview | Everyone | Counts only, cached for 60 seconds. |
| Users | Everyone | Actions need "Suspend / ban users"; deletion needs "Delete users and data". |
| Signup and access | Owners, admins | Mode, applications, invite codes, domains. |
| Reports and safety | Everyone | Decisions need "Handle reports". Only messages the reporter attached are shown. |
| Content moderation | Everyone | Keep and remove need "Handle reports"; rule switches need "Settings and switches". |
| Matching and AI | Owners, admins | No prompt or response text is stored or shown. |
| Communication | Owners, admins | Banners, the email send log (30 days), template tests. |
| Settings | Owners, admins | Feature switches and limits. |
| Team and audit | Owners | Roles and the append-only audit log. |
| Data and compliance | Owners, admins | Data requests, retention, consent, CSV exports (audit log CSV: owners). |

Every change in the portal asks for a reason and is written to the audit log in the same
transaction. Admin endpoints never return chat message text. The one exception is a report:
it shows the messages the reporter chose to attach.
