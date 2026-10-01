# 8. Background jobs, scheduling and email on the free runtime

- **Status:** Accepted
- **Date:** 2026-10-01
- **Supersedes:**
  - ADR 0005 (Valkey);
  - the separate always-on Arq worker process in ADR 0002, for the free deployment;
  - the open "worker" question in ADR 0003.

## Context

Skill Buddy launches on one campus in about a week, at zero cost and with no card on any
account (ADR 0004). The planned free stack (ADR 0003) is:

- Vercel Hobby for the web app;
- Render Free for the API: 512 MB, sleeps after 15 minutes without inbound traffic;
- Neon Free for PostgreSQL + pgvector;
- Upstash Free for Redis.

There is **no free always-on worker**. Yet three kinds of background work are needed:

1. **AI jobs** (ADR 0007): profile understanding, embeddings, match selection and
   explanations.
2. **Email:** login codes (ADR 0006), which are urgent and must arrive in seconds, and
   notification emails, which are not urgent.
3. **Scheduled jobs:**
   - account hard-deletion after the 30-day grace period;
   - purging expired codes and sessions;
   - pruning `auth_events`;
   - the AI backfill (ADR 0007).

Today these run on an Arq worker that polls Valkey/Redis (ADR 0002, ADR 0005).

Every figure below was checked on **2026-10-01** unless marked otherwise. Free tiers change
without notice; re-check [docs/free-tier-limits.md](../free-tier-limits.md) before relying
on them.

## Facts that shape the decision

| Fact | Source (checked 2026-10-01) |
| --- | --- |
| **Render Free spins down** "a Free web service that goes 15 minutes without receiving any inbound traffic". Waking takes about a minute. Render grants "750 Free instance hours to each workspace per calendar month". Background workers and cron jobs are **not** on the free list. | <https://render.com/docs/free> |
| **Render Free blocks outbound SMTP.** Free web services "can't send outbound network traffic on ports 25, 465, or 587" (live in all regions since September 2025). **Our `SMTPEmailSender` cannot work on Render Free**, so email must go out over an HTTPS API. | <https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports> |
| **Render Free Key Value** "do[es] not continually persist [its] state to disk", so its data is lost on restart. One instance per workspace. | <https://render.com/docs/free> |
| **Neon Free:** "100 CU-hours/project" per month, compute from 0.25 CU, scale to zero "after 5 min" of inactivity ("cannot disable"). When CU-hours run out, "your compute is suspended until the next billing period". The plans page now lists storage as "1 GB/project", while ADR 0003 and the storage budget assume 0.5 GB; see "Not verified". | <https://neon.com/docs/introduction/plans>, <https://neon.com/pricing> |
| **Upstash Free:** 500K commands/month. Free databases "are archived after a minimum of 30 days of inactivity": the instance is removed, and a backup can be restored by hand. An Arq worker polls about 5M commands/month (deployment-plan.md), ten times the quota. | <https://upstash.com/docs/redis/help/faq> |
| **GitHub Actions schedule:** "The shortest interval you can run scheduled workflows is once every 5 minutes". It "can be delayed during periods of high loads … If the load is sufficiently high enough, some queued jobs may be dropped". In public repositories, scheduled workflows "are automatically disabled when no repository activity has occurred in 60 days". Minutes on standard runners are free for public repos. | <https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows> |
| **GitHub Actions terms** (effective 2026-08-27) prohibit use "as a content delivery network or as part of a serverless application", and "any other activity unrelated to the production, testing, deployment, or publication of the software project". | <https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features> |
| **Cloudflare Workers Free:** 100,000 requests/day; **5 Cron Triggers per account** at 1-minute granularity; a cron run gets 10 ms of CPU but up to **15 min wall time**, and waiting on `fetch` is not CPU. No card needed. | <https://developers.cloudflare.com/workers/platform/limits/> |

### Free always-on runtimes (none qualify)

| Runtime | Finding (2026-10-01) | Verdict |
| --- | --- | --- |
| Render Free | Sleeps after 15 min; no free workers or cron | Our API host, but not always-on |
| Koyeb Free | Since February 2026 new accounts need a card (with a $29 pre-authorisation); the free instance is "only available to existing accounts"; it scales to zero after 1 hour idle | **Excluded** (card). This also removes it as the fallback host in ADR 0003. |
| Fly.io | No free allowance for new customers; the trial is 2 hours of machine time or 7 days | **Excluded** |
| Railway | Free plan carries $1/month of usage credit, which is not enough for an always-on 512 MB service; card requirements are reported inconsistently | **Excluded** |
| Oracle / Google Cloud / Azure always-free VMs | Need a card for sign-up verification (long-standing; not re-checked today) | **Excluded** |
| Hugging Face Spaces | Docker and CPU Spaces need a paid plan (ADR 0007) | **Excluded** |
| SnapDeploy | Third-party report: 512 MB containers with **100 hours/month**; always-on is paid | **Excluded** (not always-on) |
| JustRunMy.app | Claims free 24/7 hosting with no card; no limits or terms checked | **Not verified; not used** for student data |
| Cloudflare Workers | Always available, free, with cron. It runs JavaScript or Python on Pyodide in an isolate, so it can't run our FastAPI, psycopg or ONNX stack. | **Used only as a scheduler** (below) |

Independent surveys agree: "for an app with a continuously running backend, nothing keeps
it awake indefinitely for $0" (livemy.app, updated 2026-08-26).

### The Neon compute budget is the binding limit

At the minimum size of 0.25 CU, 100 CU-hours buys **400 hours of active database per
month, about 13 hours a day**. Every query keeps the database awake for the next 5 minutes.

So any design that touches the database while nobody is using the app spends the shared
budget. That includes polling a queue, frequent scheduler ticks, or keeping the API awake
24/7 with a pinger.

A pinger keeping Render awake around the clock would fit Render's 750 hours, but a runner
polling Postgres every few seconds would keep Neon awake all the time:

- 0.25 CU × 744 h = **186 CU-hours**;
- that is 186% of the quota, and the database would be suspended for the rest of the month.

## Options evaluated

**A. Postgres job queue, processed inside the API process.**

- Jobs are rows in a `jobs` table, claimed with `SELECT … FOR UPDATE SKIP LOCKED`, and run
  by an asyncio task started in the API's lifespan.
- Jobs survive sleep, restarts and out-of-memory kills, because the row stays in the table.
- A lease (`locked_until`) returns a job to the queue if the process dies mid-job.
- Enqueuing happens in the same transaction as the business write (a transactional outbox).
  This removes today's dual-write gap between Postgres and Redis.
- **Catches:**
  - Nothing runs while the API sleeps.
  - Jobs share 512 MB and the CPU with request handling.
  - Naive polling would burn Neon CU-hours.

**B. Scheduled GitHub Actions workflows** that wake the API or run due jobs.

- Minutes are free for this public repository.
- **Rejected:**
  - the terms forbid using Actions "as part of a serverless application", and running
    product jobs is "unrelated to the production, testing, deployment, or publication" of
    the software;
  - the schedule is at least 5 minutes apart, can be delayed or dropped, and is disabled
    after 60 days without commits;
  - running jobs on a runner would also send student data to GitHub infrastructure.
- Actions stays what it is: CI and the manual "Migrate staging" deployment step.

**C. A free always-on runtime.** None exists without a card; see the runtimes table.

**D. A Cloudflare Worker cron as the scheduler for A.**

- A 15-line Worker calls `POST /api/v1/admin/jobs/tick` with a secret header on a fixed
  schedule.
- The call wakes Render. The tick endpoint enqueues due scheduled jobs (idempotent, keyed
  by date), returns `202`, and the in-API runner drains the queue.
- **Catches:**
  - one more account (Cloudflare, already needed for Workers AI);
  - 5 triggers per account;
  - each tick that lands while the app is idle costs about 5 minutes of Neon compute.

**E. Where the embedding model runs.**

| Option | Assessment |
| --- | --- |
| **In the API process** | bge-small via ONNX needs about 170–230 MB, peaking near 375 MB with the app (published figures; ADR 0007). It fits under 512 MB only with: one uvicorn process, 1 ONNX Runtime thread, batches of 8 or fewer, inputs of 256 tokens or fewer, and AI jobs run one at a time. Embedding briefly slows requests on the shared CPU. An out-of-memory kill restarts the whole API. |
| Cloudflare Workers AI (`@cf/baai/bge-small-en-v1.5`) | Uses no RAM and about 2 neurons per profile. The text leaves our servers (that text already goes to Cloudflare or Groq for parsing), so the privacy wording in ADR 0007 would have to change. |
| GitHub Actions, Hugging Face Space, separate free host | Excluded above (terms, paid plan, or no host exists) |

**F. Dropping Valkey/Redis from the free deployment.**

Today Valkey carries the Arq queue, the auth rate limits and health checks; the AI budget
counters (ADR 0007) are planned for it.

- Upstash Free can't host an Arq worker, and its databases are archived after 30 idle days,
  which a quiet vacation month could cause.
- Render Key Value loses its data on restart.
- With option A, the only remaining uses are counters. Postgres handles them with an
  `INSERT … ON CONFLICT … DO UPDATE SET count = count + 1 RETURNING count` upsert, at
  campus traffic levels.
- **Yes: drop it.** Dropping it everywhere (dev, CI and staging), not just on the free host,
  keeps one code path, so CI tests exactly what runs in production.

### Email delivery

Requirements:

- reach any college address (often Google Workspace or Microsoft 365);
- send over HTTPS, because Render Free blocks SMTP;
- free, with no card;
- deliverable.

We own no domain, and buying one costs money.

| Service | Free tier | Domain needed? | Verdict |
| --- | --- | --- | --- |
| **Gmail API** from a dedicated Gmail account (`gmail.send` scope, OAuth refresh token) | Personal accounts: **500 recipients per rolling 24 hours** (counted per recipient; over the limit, sending stops with "Daily sending quota exceeded" until the window clears). HTTPS, so not blocked. No card. | **No.** Mail is signed by Google as `gmail.com` and passes SPF, DKIM and DMARC. | **Chosen** |
| Brevo | 300 emails/day, no card, HTTPS API | **Effectively yes.** Brevo says free-mail domains like `gmail.com` "cannot be authenticated", and unauthenticated mail is likely to be rejected by Gmail, Yahoo and Microsoft. | Best choice **once we own a domain** |
| Resend | 3,000/month, 100/day | **Yes.** Without a verified domain it can send only to the account owner's address ("You can only send testing emails to your own email address"). | Excluded until we own a domain |
| SMTP2GO / Mailjet | 1,000/month / 200 per day (third-party figures) | Same DMARC problem without a domain | Excluded for now |
| MailerSend, Amazon SES, SendGrid trial | n/a | n/a | Excluded (card or trial-only) |
| Gmail SMTP with an app password | 500/day | No | **Blocked** on Render Free (ports 465/587) |

**Gmail API catches:**

- The Google Cloud OAuth app must be **published "In production"**. In "Testing", refresh
  tokens for sensitive scopes such as `gmail.send` "expire in 7 days".
- Publishing without Google's verification is fine for a single user (the owner), who
  clicks through the "unverified app" warning once.
- Sending looks less official (`skillbuddy.<something>@gmail.com`).
- Google can limit or suspend an account that looks like bulk or automated mail. Volume
  must stay low and every message must be one the student asked for.
- One account is one point of failure. Opening extra accounts to get around the limit is
  not allowed and not planned.

**Enforcing the limit in our code:**

- An `email_log` table holds metadata only: purpose, keyed hash of the recipient, sent_at,
  provider message id. It is kept for 30 days.
- The email job counts recipients in the trailing 24 hours and stops at
  **`EMAIL_DAILY_CAP=450`**, below Google's 500.
- Login codes always have priority. Notification emails are sent only while more than
  `EMAIL_RESERVE_FOR_CODES=150` of the cap is left. Otherwise they wait for the next day's
  digest, and the in-app notification still shows.
- When the cap is reached, `POST /api/v1/auth/otp/request` returns `503 email_quota_exhausted` ("try
  again later") in the standard envelope.
- Notification emails are one daily digest per user at most, and only for users who opted
  in.

**Capacity:** sessions last 30 days (sliding), so codes are needed mainly at sign-up and on
new devices. 450 per day covers invite waves of about 300 students a day (ADR 0007), plus
resends and notifications.

**Testing deliverability to the student domain** (before launch, and after any change to
the sender or template):

1. Look up the college's mail host: `nslookup -type=mx <college-domain>` shows Google
   Workspace or Microsoft 365.
2. With consent, send real login codes to 3–5 volunteer student addresses, plus a Gmail and
   an Outlook.com test inbox. Record inbox, junk or quarantine for each.
3. On each received message, open the original headers ("Show original" in Gmail,
   "View message details" in Outlook) and confirm `spf=pass`, `dkim=pass`, `dmarc=pass`.
4. Run the template through a free spam-score checker.
5. If messages land in quarantine (common with Microsoft 365 for first-time senders), ask
   college IT to allow-list the sender address.
6. Keep the email plain: a short text with the code, the product name, and no links other
   than the app's own URL.

## Decision

1. **Job queue in PostgreSQL, run inside the API process on free hosting.**
   - **Table.** A `jobs` table holds: kind, payload (`jsonb`, IDs only), status, priority,
     `run_at`, attempts and max attempts, `locked_until`, a unique `dedupe_key`, a truncated
     `last_error` with no personal data, and timestamps.
   - **Claiming.** Jobs are claimed with `FOR UPDATE SKIP LOCKED`, with a lease and
     exponential backoff. They become `dead` after max attempts.
   - **Retention.** Succeeded rows are deleted after 7 days and dead rows after 30.
   - **Runner.** The runner is a module (`app/jobs/`), not a process. It starts inside the
     API when `JOBS_RUN_IN_API=true` (free hosting). Where a budget allows, it can instead
     run as its own process (`python -m app.jobs.worker`), as in the dev stack and CI.
     ADR 0002's module boundary stays: request handlers never call models, and jobs do.
   - **No idle polling.** The runner queries the database only:
     - at start-up;
     - when this process enqueues a job (an in-process signal);
     - when the earliest known `run_at` comes due;
     - on a tick.

     It holds no idle database connection open.
   - **Secret payloads never touch the table.** A login code stays only in the process's
     memory, keyed by job ID. If the process dies first, the job finishes as "expired
     unsent", and the student asks for a new code, which expires in minutes anyway.
   - **Concurrency.** AI jobs run one at a time, to protect RAM. Email and HTTP-bound jobs
     may run two at a time.
2. **Scheduler: one Cloudflare Worker cron** calling `POST /api/v1/admin/jobs/tick` with a
   `JOBS_TICK_TOKEN` header. The schedule has 2 triggers:
   - hourly from 08:00 to 23:00 IST (02:30–17:30 UTC);
   - once at 06:00 IST (00:30 UTC), for retention and the AI backfill after Cloudflare's
     neuron reset.

   That is 17 ticks a day, at most about 0.35 CU-hours a day (about 11 a month) when every
   tick lands on an idle database.
3. **No Valkey/Redis anywhere.**
   - Auth rate limits move to a Postgres fixed-window counter table, pruned hourly.
   - The AI budget counters are built on the same table.
   - The readiness check drops the Redis probe.
   - Arq and redis-py are removed.
4. **Embedding model in the API process** (ADR 0007), behind a measured gate:
   - CI records peak RSS, which must stay under 400 MB;
   - if production RSS on Render passes 430 MB, set `EMBEDDING_BACKEND=cloudflare`, update
     the privacy wording, and re-embed.
5. **Email via the Gmail API**:
   - new `GmailApiEmailSender` over HTTPS with a refresh token;
   - an `EMAIL_DAILY_CAP` of 450 in a rolling 24 hours, with a reserve for login codes;
   - `SMTPEmailSender` and Mailpit stay for dev and CI.

   Move to Brevo with an authenticated domain as soon as a domain exists: from a future
   budget, or a subdomain from the college.
6. **Neon guard:**
   - cap autoscaling at 0.25 CU;
   - expose Neon compute use on the admin storage endpoint, or check it weekly by hand
     until that exists;
   - treat 70% of CU-hours before day 21 of the month as a warning to act on.

## Consequences

**Positive**

- Zero cost, no card. One fewer service: no Upstash account and no Redis to archive.
- Jobs are durable and transactional with the data they belong to, which is better than
  today's Redis enqueue after the commit.
- Login codes no longer need Redis to stay secret, because they never sit in a store.
- One code path in dev, CI and production. The separate-worker option stays open for when
  there is a budget.
- Email reaches any address with Google-grade SPF, DKIM and DMARC alignment, and no domain
  purchase.

**Negative / risks**

- **Nothing runs while the API sleeps.** Login emails are unaffected, because the student's
  own request wakes the API. Scheduled work runs only on ticks, so housekeeping may run late,
  but it is safe to run late or twice.
- **The first request after a sleep takes about a minute** (unchanged from ADR 0003). A
  student waiting for a code sees the wake-up delay first.
- **512 MB is shared** by the API, the job runner and the embedding model. An out-of-memory
  kill takes the API down for about a minute; leases recover the jobs.
- **Neon compute is the binding limit.** About 13 active hours a day on average. A campus
  of 300–500 daily active users, spread across 16 waking hours, may run the database out of
  CU-hours in the last days of a month, which suspends it until the 1st: a full outage.
  Mitigations: the 0.25 CU cap, no idle polling, few ticks, and monitoring. The zero-cost
  escape is moving to another free Postgres (for example Supabase Free, not evaluated here),
  which needs its own ADR.
- **Email depends on one Gmail account** and on Google's tolerance for app-generated mail.
  Over 450 a day, sign-in stops until the window clears. If the college uses Google
  Workspace, a later "Sign in with Google" option (planned in ADR 0006's identity table)
  would remove most code emails.
- **Cloudflare becomes critical for scheduling.** If the Worker stops, retention jobs stop.
  An admin page showing the last tick time makes this visible.
- Supersedes ADR 0005 entirely, plus the always-on worker in ADR 0002 and its Valkey and
  Arq parts. Those status lines are updated in this PR.

## Migration from the current Arq worker

| Today (Arq + Valkey) | After |
| --- | --- |
| `app/worker/settings.py` (`WorkerSettings`, cron at 03:00/03:30 UTC) | `app/jobs/` (registry, `enqueue()`, runner, schedule table); the API lifespan starts the runner when `JOBS_RUN_IN_API=true` |
| `send_login_code(email, code)` enqueued with `_expires`, `keep_result=0` | Job row with the OTP ID only; the code is in process memory; same TTL |
| `hard_delete_accounts`, `purge_auth_data` crons | Scheduled kinds enqueued by tick with `dedupe_key="<kind>:<UTC date>"`; same idempotent service calls |
| `app/services/auth/rate_limit.py` on Redis | Same interface on a Postgres counter table |
| `app.state.redis` in `main.py`, health, storage monitor and deps | Removed; storage monitor caching moves to process memory |
| `docker-compose` services `valkey` + `worker` (Arq) | `valkey` removed; `worker` runs `python -m app.jobs.worker` (dev/CI keep a separate process; staging runs in the API) |
| Deps `arq`, `redis<6`; Dependabot ignore for redis | Removed |
| `REDIS_URL` setting | Removed; adds `JOBS_RUN_IN_API`, `JOBS_TICK_TOKEN`, `EMAIL_BACKEND=gmail_api`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_SENDER`, `EMAIL_DAILY_CAP`, `EMAIL_RESERVE_FOR_CODES` |

Storage growth:

- `jobs`: about 300 B per row, 7–30 days kept; under 1 MB at campus scale.
- Rate-limit counters: pruned hourly, kilobytes.
- `email_log`: about 150 B per email, 30 days; under 2 MB.

Each gets a row in storage-budget.md in its PR.

## Build order

1. **Jobs migration:** `jobs`, `rate_limit_counters`, `email_log` tables, with retention.
2. **`app/jobs/` core:**
   - enqueue in the caller's transaction;
   - the claim/lease/backoff/dead runner;
   - the in-memory secret channel;
   - the standalone worker entry point;
   - integration tests on real Postgres (two runners never claim the same job; a job whose
     lease expires is re-run; a restart loses no job).
3. **Port the existing jobs** and the tick endpoint (`/api/v1/admin/jobs/tick`, token-guarded,
   tested for success, bad token and the duplicate tick of the same day).
4. **Postgres rate limiter;** then remove Arq, Valkey and `REDIS_URL` from code, compose, CI
   and the smoke test. Smoke still proves an emailed sign-in through Mailpit.
5. **`GmailApiEmailSender`,** the `email_log` cap and reserve, and the `503
   email_quota_exhausted` error, all tested with a fake HTTP transport.
6. **Docs:** deployment-plan.md (no Upstash, Koyeb no longer card-free, Gmail and Cloudflare
   setup steps), CLAUDE.md architecture summary, free-tier-limits.md.
7. **Owner steps in dashboards** (exact clicks to be written in deployment-plan.md):
   - create the Gmail account, a Google Cloud project with the Gmail API, and an OAuth
     client; publish it "In production";
   - obtain a refresh token through the OAuth Playground;
   - create the Cloudflare Worker with two cron triggers and the `JOBS_TICK_TOKEN` secret;
   - set the Render environment variables;
   - cap Neon autoscaling at 0.25 CU.
8. **Deliverability test** with volunteer student addresses (steps above).
   The blocking Gmail token check under "Pre-launch checks" must also pass.
9. Then ADR 0007's AI build order from its step 2 onwards.

## Pre-launch checks (blocking)

*Added 2026-10-01.* Launch does not go ahead until every item passes.

1. **The Google Cloud OAuth app is set to "In production", not "Testing".** Check this in
   Google Cloud Console under Google Auth Platform, then Audience, then Publishing status.
   In Testing mode, refresh tokens for the `gmail.send` scope expire after 7 days, which
   would silently stop all login-code emails a week after launch.
2. **The Gmail API refresh token still works more than 7 days after it was issued.**
   - Note the date the refresh token was created. It must be created *after* the app was
     switched to "In production"; a token issued while in Testing keeps its 7-day expiry.
   - On day 8 or later, send a real login code on staging and confirm it arrives. The email
     job's log must show a successful send, with no `invalid_grant` error.
   - Record the date of the passing check in the launch checklist.
   - If it fails: switch the app to "In production", issue a new refresh token, update
     `GMAIL_REFRESH_TOKEN` in the hosting dashboard, and restart the 7-day wait.

## Not verified

- **Whether idle pooled connections stop Neon from scaling to zero.** The Neon docs don't
  define "inactivity". Measure on staging: leave the API awake with an idle pool and watch
  for suspend after 5 minutes. If the pool blocks it, close idle connections or use
  `NullPool`.
- **Neon storage.** The plans and pricing pages now say "1 GB/project", against the 0.5 GB
  recorded on 2026-10-01 in ADR 0003 and storage-budget.md. Re-check before changing the
  budget.
- **Render Free CPU allocation.** Render's free page doesn't state it; third parties cite
  0.1 CPU. Embedding speed on it is unmeasured.
- **Gmail API setup.** That the Gmail API and an OAuth client need no Google Cloud billing
  account, and that an unpublished-verification app "In production" keeps a long-lived
  refresh token for its owner, come from Google's documented behaviour and developer
  reports. Neither was tested here.
- **Deliverability** to the college's domain: not tested; the steps above do that.
- **Brevo, SMTP2GO and Mailjet figures,** and the Koyeb, Railway, SnapDeploy and
  JustRunMy.app findings, come from third-party pages, except where a provider page is
  linked.
- **Cron schedule cost:** the worst case of 17 ticks a day assumes each tick wakes an idle
  Neon compute for 5 minutes. The real cost is lower when ticks overlap with traffic.
