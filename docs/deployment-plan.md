# Zero-cost staging plan

**Status:** plan only, not set up yet. Decision recorded in
[ADR 0003](adr/0003-hosting.md). Free-tier limits below were checked on **2026-10-01**;
providers change them, so re-check each pricing page before setting anything up.

Staging is where we look at the running app. CI (GitHub Actions) remains the test runner.
Total cost of this plan: **$0/month**, no payment method needed.

## The setup at a glance

```
Browser ──► Vercel (Next.js web app, free)
               │  server-side calls over HTTPS
               ▼
            Free API host (FastAPI, sleeps when idle)
               ├──► Neon (PostgreSQL 16 + pgvector, free)
               └──► Upstash (Redis, free)

GitHub Actions ──► runs `alembic upgrade head` against Neon (manual trigger)
No background worker on staging (see "The worker" below).
```

Pick regions close to each other (and to India) to keep latency down: Singapore for Render,
Neon (AWS `ap-southeast-1`) and Upstash where offered.

## Free-tier limits and catches (as of 2026-10-01)

### Vercel Hobby (web app)

| Limit | Free allowance |
| --- | --- |
| Function invocations | 1,000,000 / month |
| Active CPU | 4 CPU-hours / month |
| Fast Data Transfer | 100 GB / month |
| Deployments | 100 / day |
| Function max duration | 300 s |
| Runtime logs | 1 hour retained |

Catches:
- **Non-commercial, personal use only** (Vercel fair-use guidelines). Fine for a private
  staging site; not for a commercial launch.
- Going over a limit pauses that feature, usually **for 30 days**.
- Vercel builds Next.js its own way and does not use `frontend/Dockerfile`.
- No password protection on Hobby; use Vercel Authentication (Deployment Protection) to keep
  staging private.

### API host: Render Free (default) or Koyeb Free (fallback)

**Render Free web service**

| Limit | Free allowance |
| --- | --- |
| Instance | 512 MB RAM, shared CPU |
| Instance hours | 750 / month per workspace (all free services suspended when used up) |
| Idle sleep | After 15 minutes without traffic; waking takes about 1 minute |

Catches:
- **No pre-deploy command, shell or one-off jobs**, so migrations run from GitHub Actions.
- Render's free-tier page lists free web services as "Node.js, Python, Rails, etc." and does
  not say whether Docker-based services qualify. When creating the service, check whether the
  Free instance type is offered for the Docker runtime; if not, use the native Python runtime
  (build: `pip install uv && uv sync --frozen --no-dev`, start: `uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port $PORT`).
- Cannot receive private-network traffic; everything reaches it over its public HTTPS URL.
- **Outbound SMTP (ports 25, 465, 587) is blocked on free web services** (since September
  2025). Email must use an HTTPS API; ADR 0008 chooses the Gmail API.
- Free services may be suspended for unusually high outbound traffic.

**Koyeb Free instance (no longer a fallback):** since February 2026 new Koyeb accounts need
a card, so it is excluded ([ADR 0008](adr/0008-free-runtime-jobs-and-email.md)). It offered one instance per organisation; 512 MB RAM, 0.1 vCPU, 2 GB SSD;
scales to zero after **1 hour** without traffic; only in **Frankfurt or Washington, D.C.**
(further from India than Render Singapore).

### Neon Free (PostgreSQL + pgvector)

| Limit | Free allowance |
| --- | --- |
| Storage | 0.5 GB per project |
| Compute | 100 CU-hours per project per month, up to 2 CU |
| Idle suspend | After 5 minutes |
| Egress | 5 GB / month |
| Branches | 10 per project |
| Point-in-time restore | 6 hours (1 GB limit) |
| Extensions | `pgvector` (with HNSW) and `citext` available on every plan |

Catches:
- Running out of compute hours or egress **suspends the database until next month**;
  exceeding 0.5 GB **blocks writes**. Data is not deleted.
- Anything that queries the database keeps it awake and burns compute hours. The host's
  health check must use the liveness endpoint `/api/v1/health` (no database), not
  `/api/v1/health/ready`. Do not add an uptime pinger that hits the readiness endpoint.
- First query after a suspend is slower while compute starts.
- 0.5 GB is ample for staging, but embeddings (384 floats ≈ 1.5 KB each, ×4 facets per user,
  plus the HNSW index; see storage-budget.md) take a large share as seeded profiles grow.

### Upstash Free (Redis)

| Limit | Free allowance |
| --- | --- |
| Databases | 1 |
| Data size | 256 MB |
| Commands | 500,000 / month |
| Bandwidth | 10 GB / month |
| Max request size | 10 MB |

Catches:
- Over the command limit, every command fails with `ERR max requests limit exceeded` until
  you upgrade or the month resets. Operational commands such as `PING` are not counted, so
  the readiness check is free.
- **An Arq worker would exhaust the quota in about 3 days**: it polls Redis about twice a
  second (~5 million commands/month). This is the main reason staging has no worker.
- Connections use TLS; Upstash gives a `rediss://` URL.

### The worker

There is no free always-on background worker on any of these providers. Options:

1. **Phase 0 (now): no worker on staging.** The only job is `ping`, so nothing is lost.
2. **Phase 1, staging only:** run jobs in-process inside the API (for example with an
   `asyncio` task queue), accepting that this bends ADR 0002 on staging only and that a
   sleeping API pauses jobs.
3. **Phase 1, proper:** pay for one small worker instance (about $7/month on Render).

**Decided in [ADR 0008](adr/0008-free-runtime-jobs-and-email.md):** a PostgreSQL job queue processed inside the API
process (no Redis at all, so Upstash is not needed), woken on a schedule by a Cloudflare
Worker cron. Setup steps are added here when it is built.

## Changes needed in the repo before setup

These are not done yet; each goes in its own PR when staging is set up.

1. **API listens on `$PORT`.** The production command in `backend/Dockerfile` hard-codes
   port 8000; hosts set `PORT` (Render defaults to 10000). Change the `CMD` to use `$PORT`
   with 8000 as the default. The image already runs as a non-root user.
2. **Database URL scheme.** Neon gives `postgresql://...?sslmode=require`, but our settings
   require `postgresql+psycopg://`. Either paste it with the scheme changed, or teach
   `app/core/config.py` to normalise `postgresql://` (with a unit test).
3. **Migration workflow.** Add a manually triggered GitHub Actions workflow ("Migrate
   staging") that runs `uv run alembic upgrade head` using a `STAGING_DATABASE_URL`
   repository secret.
4. **Status check on cold start.** The web page's API check times out after 3 seconds, so
   it shows "API unreachable" while the API wakes. Acceptable for staging; optionally
   lengthen the timeout or retry.

## Setup steps (for later)

Do these in order. Nothing secret goes in the repository: every secret is pasted into a
provider dashboard or a GitHub repository secret.

### 1. Neon (database)

1. Sign up at neon.com (GitHub login works; no card).
2. Create a project: Postgres **16**, region **AWS Asia Pacific (Singapore)**.
3. On the project dashboard, open **Connect**, turn **off** "Connection pooling", and copy
   the connection string.
4. Change its start from `postgresql://` to `postgresql+psycopg://` (unless repo change 2 is
   done). Keep `?sslmode=require` at the end. This is your `DATABASE_URL`.
5. In GitHub: repo **Settings → Secrets and variables → Actions → New repository secret**,
   name `STAGING_DATABASE_URL`, value = the URL from step 4.
6. Run the "Migrate staging" workflow (repo change 3) from the **Actions** tab. It creates
   the tables and enables `vector` and `citext`.

### 2. Upstash (Redis)

1. Sign up at upstash.com (no card).
2. **Create Database** → Redis, region **ap-southeast-1 (Singapore)**, free plan.
3. Copy the `rediss://` connection URL from the database page. This is your `REDIS_URL`.

### 3. API (Render Free)

1. Sign up at render.com with GitHub; do not add a payment method.
2. **New → Web Service**, connect the `SkillBuddy` repository, branch `main`.
3. Runtime **Docker**, Dockerfile path `backend/Dockerfile`, Docker context `backend`
   (the last stage, `runtime`, is the production image and is built by default). Use the
   native Python runtime instead if Free is not offered for Docker (see the catches above).
   Region **Singapore**, instance type **Free**.
4. **Health check path:** `/api/v1/health`.
5. Environment variables:

   | Key | Value |
   | --- | --- |
   | `ENVIRONMENT` | `staging` |
   | `SECRET_KEY` | a random string of 32+ characters (Render's "Generate" button) |
   | `DATABASE_URL` | from Neon step 4 |
   | `REDIS_URL` | from Upstash step 3 |
   | `CORS_ALLOW_ORIGINS` | the Vercel URL from step 4 below (fill in after it exists) |
   | `API_DOCS_ENABLED` | `true` (staging only) |

6. **Settings → Build & Deploy → Auto-Deploy → "After CI Checks Pass"**, so nothing deploys
   unless GitHub Actions is green on `main`.
7. Note the public URL, e.g. `https://skillbuddy-api.onrender.com`.

### 4. Web app (Vercel Hobby)

1. Sign up at vercel.com with GitHub (Hobby, no card).
2. **Add New → Project**, import `SkillBuddy`, set **Root Directory** to `frontend`.
   Vercel detects Next.js.
3. Environment variable: `API_INTERNAL_URL` = the API's public URL from step 3.7.
4. Deploy. Copy the production URL (e.g. `https://skillbuddy.vercel.app`) into the API's
   `CORS_ALLOW_ORIGINS` and redeploy the API.
5. Optional: **Settings → Deployment Protection → Vercel Authentication** to keep staging
   private.
6. Vercel deploys every push to `main`. To deploy only after CI passes, set up a GitHub
   ruleset requiring the CI checks before merging into `main` (all changes arrive by PR).

## Day-to-day

- **Logs:** Render service → **Logs** tab (API). Vercel project → **Logs** (1 hour kept on
  Hobby). Neon and Upstash dashboards show usage against the free limits.
- **Rollback:** Render service → **Events** → pick an earlier deploy → **Rollback**. Vercel
  project → **Deployments** → earlier deployment → **Instant Rollback** (on Hobby this may be
  limited to the previous production deployment). Rollbacks do not undo database
  migrations; revert a migration with a new PR instead.
- **Watch the meters** monthly: Neon compute hours, Upstash commands, Render instance hours.
  If one is near its limit, staging will stop until the month resets.

## When to move off this plan

Move to paid hosting (new ADR) before any commercial use (Vercel Hobby terms), when staging
needs an always-on worker, or when cold starts get in the way of testing.
