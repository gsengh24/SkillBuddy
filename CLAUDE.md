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

## Architecture summary

- **Modular monolith + worker** (ADR 0002). One backend codebase, two processes:
  - **API** (FastAPI): HTTP only. It never calls an LLM or embedding model. Slow work is
    persisted and enqueued, and the API returns immediately.
  - **Worker** (Arq on Redis): runs background jobs, including every model call.
- **PostgreSQL 16 + pgvector** is the single source of truth, including embeddings.
  **Redis** is the queue and cache.
- **Next.js** web app. Server components call the API through a typed client.
- Migrations run as a **separate one-shot step** (`migrate` service), never at API startup.

## Folder map

```
backend/
  app/
    main.py              App factory (create_app) + lifespan (DB engine, Redis pool)
    core/                config (settings), logging (JSON), errors (envelope + handlers),
                         request_context (request-id middleware), security (stubs, headers)
    db/                  base (DeclarativeBase, naming convention, mixins), engine, session
    models/              SQLAlchemy models; import new ones in models/__init__.py
    schemas/             Pydantic request/response models
    api/deps.py          Shared FastAPI dependencies
    api/v1/              Routers; router.py aggregates them under /api/v1
    services/            Business logic; endpoints and jobs call these
    worker/              Arq settings (settings.py) and job functions (jobs.py)
  migrations/            Alembic env + versions (one file per migration)
  tests/unit/            No infrastructure needed
  tests/integration/     Real Postgres + Redis; each run uses a throwaway database
frontend/
  app/                   App Router pages and route handlers (app/api/health = web liveness)
  components/            React components
  lib/brand.ts           Product name and copy (the only place the name is defined)
  lib/env.ts             Server env validation (zod)
  lib/api/               Typed API client + response schemas
infra/                   Deployment notes, production env template
docs/                    ARCHITECTURE.md, adr/
```

## Commands

All from the repo root; they run inside Docker.

| Task | Command |
| --- | --- |
| Start / stop | `make up` / `make down` |
| Logs | `make logs` or `make logs s=api` |
| Test (backend) | `make test` |
| Lint + typecheck (all) | `make lint` |
| Format (all) | `make format` |
| Apply migrations | `make migrate` |
| Revert one migration | `make downgrade` |
| New migration | `make revision m="describe change"` |
| DB shell | `make psql` |

Without Docker: `cd backend && uv run pytest tests/unit`, `uv run ruff check .`,
`uv run mypy`; `cd frontend && npm run lint && npm run typecheck && npm run build`.

## Rules (non-negotiable)

1. **Never commit secrets.** No keys, tokens, passwords or real personal data in code,
   tests, fixtures, logs or docs. Configuration comes from the environment; document every
   variable in the relevant `.env.example`. Gitleaks runs in pre-commit.
2. **Every DB change needs an Alembic migration.** Change the model, run
   `make revision m="..."`, review and edit the generated file, and make sure `downgrade()`
   works. CI runs upgrade → downgrade → upgrade and `alembic check` (model/migration drift).
3. **Every endpoint needs tests**, covering at least the success path and the main failure
   paths (validation, not found, unauthorised). Use real Postgres/Redis in integration tests,
   not mocks of our own infrastructure.
4. **LLM calls only through the AI gateway module** (added in Phase 1). No direct provider
   SDK calls anywhere else. The gateway logs prompt version, latency, tokens and cost.
5. **All model output is schema-validated** (Pydantic) before use. Invalid output gets one
   retry, then fails loudly. Treat all user-written text as untrusted input to prompts.

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
- Jobs must be idempotent (Arq retries).
- Settings: add to `Settings` in `app/core/config.py` with a type and validation, and to
  `backend/.env.example` with a comment.

**Frontend (TypeScript strict)**
- Responsive, mobile-first layouts (Tailwind breakpoints scale up from small screens).
  Every page must work well on a phone-sized viewport.
- Server components by default; add `"use client"` only when needed.
- Talk to the API only through `lib/api/client.ts`, with a Zod schema for every response.
- Read env only through `lib/env.ts`. Never import server-only modules into client components.
- Use the brand name only from `lib/brand.ts`.
- ESLint (`--max-warnings=0`) and Prettier must pass.

**General**
- Conventional Commits; small PRs; see `CONTRIBUTING.md`.
- Prefer boring, well-supported libraries. New infrastructure or major dependencies need
  an ADR.
- Privacy by default: collect the minimum, and remember that embeddings are personal data.
