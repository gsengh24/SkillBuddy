# CLAUDE.md

Guidance for AI assistants (and humans) working in this repository.

## Project overview

An AI matchmaking platform (working name **Skill Buddy**) that introduces people to
collaborators, skill partners and interest buddies. Users describe themselves in free text;
the system extracts structure, embeds several facets of each profile, retrieves and ranks
candidates, and uses an LLM to pick and explain a few matches. Contact requires two-sided
consent.

**`docs/ARCHITECTURE.md` is the source of truth** for product scope, data model and roadmap.
Past decisions and their reasons live in `docs/adr/`. Read the relevant ADRs before
proposing structural changes; a change that contradicts one needs a new ADR.

**Product shape:** a responsive web application (Next.js frontend + FastAPI backend). Not a
mobile app, not a script. A native mobile app may come much later, so the API must stay
clean and frontend-agnostic (see "API design" below).

Current phase: **Phase 0 (foundations)**. Do not build Phase 1+ features unless asked.

## How we work

**Where things run.** The developer laptop has no Docker and never runs the app.

| Where | What runs there |
| --- | --- |
| Laptop | Editing, git, and checks that need no Docker, Postgres or Redis |
| GitHub Actions CI | The test runner: lint, types, migrations, unit + integration tests, image builds |
| Staging site | The running app, for seeing changes (hosting not set up yet) |
| GitHub Codespaces | Optional: the full stack via `docker compose` (`.devcontainer/`) |

**Workflow rules**

1. Work on a short-lived feature branch (`<type>/<short-description>`). Never push directly
   to `main`; every change goes through a pull request.
2. Never try to run Docker, Postgres or Redis on the laptop. Run only the local checks below
   and rely on CI for everything else.
3. A task is done only when its PR's CI is green. Say so with the job names that passed.
   Required checks on `main` (GitHub ruleset "Protect main"): Backend, Frontend,
   Docker images, Smoke, Secret scan.
4. If CI fails, read the logs (`gh run view --log-failed`, or ask for them to be pasted), fix
   the cause and push again. Never disable, skip or weaken a check, test or threshold to get
   green.
5. Every PR description states what changed, how it was verified (which CI jobs passed, which
   local checks ran) and anything not verified. Use `.github/pull_request_template.md`.

## Architecture summary

- **Modular monolith + worker** (ADR 0002). One backend codebase, two processes:
  - **API** (FastAPI): HTTP only. It never calls an LLM or embedding model. Slow work is
    persisted and enqueued, and the API returns immediately.
  - **Jobs** ([ADR 0008](docs/adr/0008-free-runtime-jobs-and-email.md)): a PostgreSQL job
    queue (`app/jobs/`, `SKIP LOCKED` with leases). Every model call runs in a job.
    `python -m app.jobs.worker` runs jobs as a separate process (dev stack, CI); on free
    hosting `JOBS_RUN_IN_API=true` runs them all inside the API process. Login-code emails
    always run in the API process that enqueued them (the code is never stored).
  - **Scheduling:** no cron process. The scheduler (a Cloudflare Worker cron) calls
    `POST /api/v1/admin/jobs/tick`, which enqueues due daily and hourly jobs once per period.
- **PostgreSQL 16 + pgvector** is the single source of truth, including embeddings and jobs.
  **Valkey** (Redis-compatible, ADR 0005) holds rate limits and a cache until ADR 0008
  step 4 moves them to PostgreSQL.
- **Next.js** web app. Server components call the API through a typed client; the browser
  calls the web app's own `/api/v1/*`, which forwards to the API (same-origin cookies).
- **Authentication** (ADR 0006): passwordless email codes, server-side sessions in an
  httpOnly cookie, signed double-submit CSRF, Valkey rate limits, 30-day deletion grace
  period. Email is sent only by background jobs (Mailpit catches it in dev and CI). 18+ only, by
  a required self-declaration tick box; no verification (ADR 0009).
- Migrations run as a **separate one-shot step** (`migrate` service), never at API startup.

## Folder map

```
backend/
  app/
    main.py              App factory (create_app) + lifespan (DB engine, Valkey pool)
    core/                config (settings), logging (JSON), errors (envelope + handlers),
                         request_context (request-id middleware), security (stubs, headers)
    db/                  base (DeclarativeBase, naming convention, mixins), engine, session
    models/              SQLAlchemy models; import new ones in models/__init__.py
    schemas/             Pydantic request/response models
    api/deps.py          Shared FastAPI dependencies
    api/v1/              Routers; router.py aggregates them under /api/v1
    services/            Business logic; endpoints and jobs call these
      auth/              Sign-in codes, sessions, rate limits, audit log, retention jobs
      email/             EmailSender (console/SMTP) and templates
      storage.py         Database size monitor and the 90% write pause
    jobs/                Job queue: registry, enqueue, runner, tasks (every job kind),
                         schedule (tick), worker (stand-alone process entry point)
  migrations/            Alembic env + versions (one file per migration)
  evals/                 Matcher evaluation set: synthetic profiles + draft-labelled pairs
  tests/unit/            No infrastructure needed
  tests/integration/     Real Postgres + Valkey; each run uses a throwaway database
frontend/
  app/                   App Router pages: /login, /terms, /privacy; signed-in pages in app/(app)/
                         (/home, /messages, /saved, /notifications, /settings/account) share
                         the app shell; /design is the style guide (development only)
  app/api/v1/[...path]/  Same-origin forwarder to the API (app/api/health = web liveness)
  proxy.ts               Next.js Proxy: sends signed-out visitors of protected pages to /login
  components/ui/         Design-system components (Button, Card, IntentChip, ...; ADR 0010)
  components/shell/      App shell: desktop sidebar, phone top row and tab bar
  components/            Other React components (auth, legal)
  lib/design/            Design tokens (source of truth), colour helpers, contrast pairs
  lib/brand.ts           Product name and copy (the only place the name is defined)
  lib/env.ts             Server env validation (zod)
  lib/api/               Typed API clients (client.ts server, browser.ts browser) + schemas
  lib/auth/              Session check (server), cookie names, redirects, error messages
  e2e/                   Playwright end-to-end tests (run by the CI Smoke job)
.devcontainer/           GitHub Codespaces config (Docker-in-Docker; stack via docker compose)
infra/                   Deployment notes, production env template
docs/                    ARCHITECTURE.md, adr/, deployment-plan.md, free-tier-limits.md,
                         storage-budget.md, roadmap.md, phase-0-exit-report.md,
                         pre-launch-checklist.md
```

## Commands

**Local checks (laptop, no Docker).** Install dependencies once with `cd backend && uv sync`
and `cd frontend && npm ci`.

| Check | Command |
| --- | --- |
| Backend lint + format | `cd backend && uv run ruff check . && uv run ruff format --check .` |
| Backend types | `cd backend && uv run mypy` |
| Backend unit tests | `cd backend && uv run pytest tests/unit` |
| Frontend lint + types + format | `cd frontend && npm run lint && npm run typecheck && npm run format:check` |
| Frontend component tests | `cd frontend && npm test` |

Integration tests, migrations and image builds run in CI. The full stack runs only in CI or
a Codespace, with plain `docker compose` from the repo root (`make` is not assumed to exist;
`Makefile` targets are optional shortcuts):

| Task | Command |
| --- | --- |
| Start (wait until healthy) | `docker compose up --build --detach --wait` |
| Stop / wipe data | `docker compose down` / `docker compose down -v` |
| Status / logs | `docker compose ps` / `docker compose logs --follow api` |
| Test (backend) | `docker compose run --rm --no-deps api pytest --cov --cov-report=term-missing` |
| Lint + typecheck (backend) | `docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check . && mypy"` |
| Lint + typecheck (frontend) | `docker compose run --rm --no-deps web sh -c "npm run lint && npm run typecheck && npm run format:check"` |
| Apply migrations | `docker compose run --rm migrate alembic upgrade head` |
| Revert one migration | `docker compose run --rm migrate alembic downgrade -1` |
| New migration | `docker compose run --rm migrate alembic revision --autogenerate -m "describe change"` |
| DB shell | `docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'` |

## Rules (non-negotiable)

1. **Never commit secrets.** No keys, tokens, passwords or real personal data in code,
   tests, fixtures, logs or docs. Configuration comes from the environment; document every
   variable in the relevant `.env.example`. Staging and production secrets are set in the
   hosting dashboard, never in the repo. Gitleaks runs in pre-commit.
2. **Every DB change needs an Alembic migration.** Change the model, generate one with
   `alembic revision --autogenerate` (see Commands), review and edit it, and make sure
   `downgrade()` works. CI runs upgrade → downgrade → upgrade and `alembic check`.
3. **Every endpoint needs tests**, covering at least the success path and the main failure
   paths (validation, not found, unauthorised). Use real Postgres/Redis in integration tests,
   not mocks of our own infrastructure.
4. **LLM calls only through the AI gateway module** (added in Phase 1). No direct provider
   SDK calls anywhere else. The gateway logs prompt version, latency, tokens and cost.
5. **All model output is schema-validated** (Pydantic) before use. Invalid output gets one
   retry, then fails loudly. Treat all user-written text as untrusted input to prompts.

## Zero-cost constraint

No money is spent on this project for the foreseeable future (ADR 0004). Everything runs on
free tiers or open-source software, with no credit card on any account.

1. **No paid services, paid-only dependencies, or anything that needs a card.** Before
   adding an external service or API, check its current free tier and record limits and
   catches (sleeping, size caps, rate limits, data-use terms), dated, in
   [docs/free-tier-limits.md](docs/free-tier-limits.md).
2. **AI gateway, LLM-first** ([ADR 0007](docs/adr/0007-ai-gateway.md)). All LLM and
   embedding calls go through the gateway, in background jobs. The LLM is a core stage
   (profile understanding, final selection, explanations) used for every match request by
   default, on free providers that forbid training on inputs (Groq, then Cloudflare Workers
   AI). Embeddings come from an open-source model run locally on CPU (bge-small-en-v1.5).
   The rule-based, template-explanation path is a **fallback only**, used when quotas run
   out, providers fail or the `AI_LLM_ENABLED` kill switch is off; matching must still
   work end to end on it. Respect the daily caps and timeout. Send only redacted free text
   and alias-labelled summaries, never names, emails or contact handles.
3. **Embedding dimension is a setting plus a migration**, never assumed in code. ADR 0007
   chose 384 (migration 0004 changed the column from 768). Settings refuse any other
   `EMBEDDING_DIMENSIONS`, and embedding jobs check the column before writing. The CI memory
   check keeps the API process plus the model under 400 MB.
4. **Real user data never goes to a free-tier API whose terms allow training on inputs.**
   Use synthetic data for development and evaluation.
5. **Every feature has a hard usage cap** and fails gracefully ("try again later") when a
   free limit is hit, instead of running up cost or crashing.
6. **Keep CI cheap:** cache dependencies, run the full pipeline only on pull requests and
   `main`, keep the Dependabot open-PR limit low.
7. **Stay small:** prefer slim Docker images and low memory use; free hosts have little RAM.

## Storage rules

The free database holds 0.5 GB; we budget 70% of it (numbers in
[docs/storage-budget.md](docs/storage-budget.md)). Every task follows these rules:

1. **Cap text sizes** with validation limits on every user-written field (profile text,
   request text, messages). **No file or image uploads**: use initials avatars or links.
2. **Retention from day one.** Every table that grows over time ships with its retention
   policy: expired OTP codes and sessions purged daily; `auth_events` and `events` pruned or
   aggregated after a set number of days; soft-deleted accounts hard-deleted on schedule.
3. **No raw LLM prompts or responses** stored beyond a short debug window; keep metadata
   (prompt version, tokens, latency) instead.
4. **Compact storage:** smallest workable embedding dimension, no duplicated data, no
   unused indexes.
5. **Size monitor:** database size is exposed as a metric on a protected admin or health
   endpoint. At 70% it warns; at 90% the app pauses new signups and non-essential writes
   and users see a clear message, not errors.
6. **PR description:** every migration that adds a growing table states its retention and
   estimated growth, and adds a row to `docs/storage-budget.md`.

## API design (frontend-agnostic)

The web app is the first client of the API, not the only one. Design every endpoint as if a
mobile app were calling it tomorrow.

- Versioned REST + JSON under `/api/v1`. The OpenAPI schema is the contract; keep it
  accurate (response models, status codes, error responses).
- No presentation concerns in the API: no HTML, no UI copy, and no response shapes tailored
  to one screen. Return resources and let each client compose them.
- Authentication must work for non-browser clients (bearer tokens). Cookie sessions for the
  web, if used, are a layer on top, not the only mechanism.
- One error envelope (`{"error": {...}}`), stable machine-readable `code`s, and consistent
  conventions (UTC ISO-8601 timestamps, UUIDs, cursor pagination) across all endpoints.
- The frontend gets data only from public API endpoints. Never add web-only backdoors, and
  never put business logic in Next.js that another client would have to duplicate.
- Breaking changes go in a new API version, not into `/api/v1`.

## Coding standards

**Backend (Python 3.12)**
- Types everywhere; `mypy --strict` must pass. No bare `# type: ignore`; always give the
  error code and a reason.
- Ruff for lint and formatting (line length 100). Don't disable rules inline without a reason.
- Async all the way: async SQLAlchemy sessions, `redis.asyncio`, no blocking I/O in handlers.
- Endpoints stay thin: validate input (schemas), call a service, return a schema. Business
  logic lives in `services/`. Modules interact only through each other's service functions.
- Raise `AppError` subclasses (`app/core/errors.py`) for expected failures; never return
  ad-hoc error dicts. Every error response uses the `{"error": {...}}` envelope.
- Log with `logging.getLogger(__name__)` and structured `extra={...}` fields; logs are JSON.
  Never log secrets, tokens or raw profile text.
- Models: UUID primary keys, `timestamptz` columns, constraint names from the naming
  convention, `CHECK` constraints instead of Postgres enums (cheaper to migrate).
- Jobs must be idempotent (the runner retries, and an expired lease runs a job again).
- Protect endpoints with `Depends(get_current_user)` (or `get_optional_user`). Cookie-
  authenticated writes are CSRF-checked automatically; never bypass that dependency.
- Send email only from worker jobs through `EmailSender`; never log codes, tokens or full
  email addresses (use `mask_email`).
- Add `Depends(require_storage_capacity)` to endpoints that make non-essential writes.
- Settings: add to `Settings` in `app/core/config.py` with a type and validation, and to
  `backend/.env.example` with a comment.

**Frontend (TypeScript strict)**
- Responsive, mobile-first layouts (Tailwind breakpoints scale up from small screens).
  Every page must work well on a phone-sized viewport.
- Server components by default; add `"use client"` only when needed.
- Talk to the API only through `lib/api/client.ts` (server) or `lib/api/browser.ts` (browser,
  same-origin, sends the CSRF header), with a Zod schema for every response.
- Protected pages call `getCurrentUser()` (`lib/auth/session.ts`) and redirect when it is
  null; `proxy.ts` is only a fast first check.
- Read env only through `lib/env.ts`. Never import server-only modules into client components.
- Use the brand name only from `lib/brand.ts`.
- **Design system** ([docs/design/design-system.md](docs/design/design-system.md), ADR 0010):
  build screens from `components/ui` and the shell. Only token colours (Tailwind's default
  palette is removed); never a hue's base colour for text; no animations or transitions;
  outline buttons only; 44px touch targets on phones. A person's colour comes only from
  `personHue(userId)`. Add colours to `lib/design/tokens.ts` and `app/globals.css` together.
- ESLint (`--max-warnings=0`) and Prettier must pass.

**General**
- Conventional Commits; small PRs; see `CONTRIBUTING.md`.
- Prefer boring, well-supported libraries. New infrastructure or major dependencies need
  an ADR.
- Privacy by default: collect the minimum, and remember that embeddings are personal data.
