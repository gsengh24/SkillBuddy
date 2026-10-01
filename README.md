# Skill Buddy

An AI matchmaking platform that introduces people to collaborators, skill partners and
interest buddies. *Skill Buddy* is a working name; see [Renaming](#renaming-the-product).

> **Status: Phase 0 (foundations).** This repository contains a production-grade skeleton:
> API, background worker, database schema, web app, Docker, CI. It has no product features
> yet. The plan lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Stack

| Layer | Technology |
| --- | --- |
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic, psycopg 3 |
| Background jobs | Arq on Valkey (Redis-compatible) |
| Database | PostgreSQL 16 + pgvector |
| Web | Next.js (App Router), TypeScript (strict), Tailwind CSS |
| Local dev | Docker Compose |
| CI | GitHub Actions |

## How we work

- **No local app.** Docker is not used on the development laptop. GitHub Actions CI is the
  test runner, and a staging site (not set up yet) is where the running app is checked.
  A Codespace can run the full stack when needed (see below).
- **Locally, run only checks that need no Docker, Postgres or Redis:** Ruff, mypy, backend
  unit tests, and frontend lint, typecheck and format checks. Commands are in
  [CLAUDE.md](CLAUDE.md#commands).
- **Branches and PRs.** Every change goes on a short-lived feature branch and through a pull
  request; nothing is pushed directly to `main`. A change is done when its CI is green.
- **Red CI is fixed, not bypassed.** Read the failing job's logs, fix the cause and push
  again. Checks, tests and thresholds are never disabled or weakened to get green.
- **Secrets** never go in the repo. Staging and production secrets are set in the hosting
  dashboard.
- **PR descriptions** state what changed, how it was verified (which CI jobs passed) and what
  was not verified.

## Develop in Codespaces

No local Docker needed: the whole stack runs inside a GitHub Codespace via
Docker-in-Docker. The setup lives in [.devcontainer/](.devcontainer/).

1. On GitHub, open the repository, click **Code → Codespaces → Create codespace on main**.
   (The config requests a machine with at least 8 GB RAM.)
2. Wait for the post-create step to finish. It installs the backend dependencies
   (`uv sync`), the frontend dependencies (`npm ci`) and the git pre-commit hooks. The
   editor extensions (Python, Ruff, Mypy, ESLint, Prettier, Tailwind CSS) install
   automatically.
3. In the Codespace terminal, start the stack and wait until every service is healthy
   (the first build takes a few minutes):
   ```bash
   docker compose up --build --detach --wait
   docker compose ps
   ```
4. Open the **Ports** tab. Port **3000** is the web app (the status panel should read
   **API connected**) and port **8000** is the API (add `/docs` for the interactive docs).

**Signing in on the dev stack.** Open `/login` on port 3000, enter any email address and tick
the terms box. The worker sends the 6-digit code to **Mailpit** (port **8025**), which
catches every email; nothing leaves the Codespace. Authentication is described in
[ADR 0006](docs/adr/0006-authentication-and-sessions.md); [ADR 0009](docs/adr/0009-minors-permitted.md)
removed its age requirement.

Everyday commands, run from the repository root:

```bash
docker compose logs --follow api                         # follow one service's logs
docker compose run --rm migrate alembic upgrade head     # apply migrations
docker compose run --rm migrate alembic downgrade -1     # revert one migration (or: base)
docker compose run --rm migrate alembic revision --autogenerate -m "describe change"

# Backend tests (unit + integration against the real Postgres, Valkey and Mailpit)
docker compose run --rm --no-deps api pytest --cov --cov-report=term-missing

# Lint and type-check
docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check . && mypy"
docker compose run --rm --no-deps web sh -c "npm run lint && npm run typecheck && npm run format:check"

docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'   # database shell
docker compose down                                     # stop (add -v to wipe data)
```

Stop the Codespace from GitHub when you are done; it does not need to keep running for
your changes to be kept, but uncommitted work only lives in that Codespace until pushed.

## Quick start (any machine with Docker)

Optional: the owner's laptop does not run Docker (see [How we work](#how-we-work)); CI and
Codespaces run the stack there. On a machine that has Docker:

**Requirements:** Docker (Desktop, or Engine with Compose v2.24+) and `make`.
On Windows without `make`, see [Windows without make](#windows-without-make) for the
equivalent `docker compose` commands.

```bash
make up          # build and start everything; returns when all services are healthy
```

Then open:

- Web app: <http://localhost:3000>. The status panel should read **API connected**.
- API docs: <http://localhost:8000/docs>
- Readiness: <http://localhost:8000/api/v1/health/ready>

No configuration is needed for local development. To change ports or credentials, copy
`.env.example` to `.env` and edit it.

`make up` runs `docker compose up --build --detach --wait`. Plain
`docker compose up --build` works too, with logs in the foreground.

### Services

| Service | What it is | Local address |
| --- | --- | --- |
| `db` | PostgreSQL 16 with pgvector | `localhost:5432` (user/password/db `app`) |
| `valkey` | Valkey 9 (Redis-compatible): job queue, cache, rate limits | `localhost:6379` |
| `mailpit` | Catches all outgoing email (sign-in codes) | <http://localhost:8025> |
| `migrate` | One-shot `alembic upgrade head`; exits when done | n/a |
| `api` | FastAPI with hot reload | <http://localhost:8000> |
| `worker` | Arq worker with hot reload | n/a |
| `web` | Next.js dev server | <http://localhost:3000> |

`api` and `worker` wait for `migrate` to complete, and `web` waits for `api` to be healthy.

## Everyday commands

| Command | What it does |
| --- | --- |
| `make up` / `make down` | Start / stop the stack (data volumes are kept) |
| `make logs` / `make logs s=api` | Follow logs for all services or one |
| `make ps` | Service status and health |
| `make migrate` | Apply migrations (`rev=<id>` for a specific target) |
| `make downgrade` | Revert one migration (`rev=base` to revert all) |
| `make revision m="add requests"` | Autogenerate a migration from model changes |
| `make test` | Backend tests: unit + integration against real Postgres and Redis |
| `make lint` | Ruff, mypy (strict), ESLint, TypeScript, Prettier |
| `make format` | Auto-format backend and frontend |
| `make psql` | psql shell on the local database |

To wipe local data, run `docker compose down -v`.

### Windows without make

Every `make` target is a thin wrapper around `docker compose`. From the repo root in
PowerShell (or any shell), run these instead:

| make | Equivalent command |
| --- | --- |
| `make up` | `docker compose up --build --detach --wait` |
| `make down` | `docker compose down` |
| `make logs s=api` | `docker compose logs --follow api` |
| `make ps` | `docker compose ps` |
| `make migrate` | `docker compose run --rm migrate alembic upgrade head` |
| `make downgrade` | `docker compose run --rm migrate alembic downgrade -1` |
| `make downgrade rev=base` | `docker compose run --rm migrate alembic downgrade base` |
| `make revision m="..."` | `docker compose run --rm migrate alembic revision --autogenerate -m "..."` |
| `make test` | `docker compose up --detach --wait db redis` then<br>`docker compose run --rm --no-deps api pytest --cov --cov-report=term-missing` |
| `make lint` | `docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check . && mypy"` then<br>`docker compose run --rm --no-deps web sh -c "npm run lint && npm run typecheck && npm run format:check"` |
| `make format` | `docker compose run --rm --no-deps api sh -c "ruff format . && ruff check --fix ."` then<br>`docker compose run --rm --no-deps web sh -c "npm run format && npm run lint:fix"` |
| `make psql` | `docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'` |

## Running without Docker (optional)

Backend (needs local Postgres with pgvector, and Redis):

```bash
cd backend
uv sync
cp .env.example .env            # set SECRET_KEY, DATABASE_URL, REDIS_URL
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload
uv run arq app.worker.settings.WorkerSettings        # in another terminal
uv run pytest tests/unit                               # no infrastructure needed
```

Frontend:

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

## Repository layout

```
backend/    FastAPI app, Arq worker, Alembic migrations, tests
frontend/   Next.js web app
infra/      Deployment notes and production environment template
docs/       ARCHITECTURE.md (source of truth) and ADRs (docs/adr)
```

See [CLAUDE.md](CLAUDE.md) for a detailed folder map and coding standards, and
[CONTRIBUTING.md](CONTRIBUTING.md) for the workflow.

## Renaming the product

The product name is defined once per app:

- Backend: `app_name` default in `backend/app/core/config.py` (overridable with `APP_NAME`)
- Frontend: `frontend/lib/brand.ts`

Internal identifiers (package names, image names, the Compose project) use the neutral name
`matchmaking` and do not need to change.

## Production

`docker-compose.prod.yml` is a reference single-host layout that uses the production image
targets. See [infra/README.md](infra/README.md).

## License

Proprietary. All rights reserved. See [LICENSE](LICENSE).
