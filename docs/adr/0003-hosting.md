# 3. Zero-cost staging hosting

- **Status:** Accepted; the worker question is settled by [ADR 0008](0008-free-runtime-jobs-and-email.md), which also
  drops Upstash and notes that Koyeb Free now needs a card for new accounts
- **Date:** 2026-10-01

## Context

We need a staging site to see the running app, because the development laptop has no
Docker and GitHub Actions CI is our only test runner. There is no budget for hosting yet,
so paid setups were ruled out. A Render blueprint with paid services (about $20–37/month)
was evaluated and rejected for cost.

Staging must run our stack: a Next.js web app, a FastAPI API, PostgreSQL with `pgvector`
(and `citext`), Redis, and, from Phase 1, an Arq background worker (ADR 0002).

## Decision

Plan staging entirely on free tiers, to be set up when we are ready:

| Component | Service | Free tier (checked 2026-10-01) |
| --- | --- | --- |
| Web (Next.js) | Vercel Hobby | Free; non-commercial use only |
| API (FastAPI) | A free web host, Render Free by default (Koyeb Free as fallback) | Sleeps when idle |
| PostgreSQL + pgvector | Neon Free | 0.5 GB storage, 100 CU-hours/month, `pgvector` and `citext` available |
| Redis | Upstash Free | 256 MB, 500K commands/month |
| Background worker | None | No free always-on worker exists |

There is **no free always-on worker**. In Phase 0 the only job is `ping`, so staging runs
without a worker. When Phase 1 adds real jobs, we choose between running jobs in-process in
the API for staging only, or paying for a worker instance; that choice gets its own ADR.

Migrations still run as a separate step (never in the API start command). Free API hosts
have no pre-deploy hook, so a manually triggered GitHub Actions job will run
`alembic upgrade head` against staging.

Details, limits and setup steps are in [docs/deployment-plan.md](../deployment-plan.md).

## Consequences

**Positive**

- Staging costs nothing, and no account needs a payment method.
- Each piece is a managed service: no servers, no Docker on the laptop.
- Postgres stays on pgvector, matching production plans; nothing in the data model changes.

**Negative / risks**

- **Cold starts.** The API sleeps after idle time (15 min on Render Free) and takes about
  a minute to wake; Neon also suspends after 5 minutes. The first page load after a pause is
  slow, and the web page may briefly show the API as unreachable.
- **Hard monthly caps.** Exceeding Neon's compute hours suspends the database until next
  month; exceeding Upstash's commands makes Redis return errors; Vercel pauses features for
  30 days. Staging can go down until the month resets.
- **No worker.** Background-job behaviour cannot be exercised on staging until Phase 1
  decides how to run it. Running Arq against Upstash Free would exhaust the command quota in
  days because the worker polls Redis continuously.
- **Terms.** Vercel Hobby is for non-commercial use only; staging must move to a paid plan
  (or another host) before the product is used commercially.
- **Different from production.** Vercel builds Next.js natively rather than from our
  Dockerfile, and free hosts are not representative of production performance.
- Provider free tiers change; limits must be re-checked before setup.

**When to revisit**

Before public launch, or as soon as staging needs an always-on worker, real performance
numbers, or commercial use. Production hosting will need a new ADR (ARCHITECTURE.md §9).
