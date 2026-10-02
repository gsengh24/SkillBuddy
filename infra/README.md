# Infrastructure

Phase 0 ships container images and a reference Compose layout. Staging is planned on free
tiers ([ADR 0003](../docs/adr/0003-hosting.md), [deployment plan](../docs/deployment-plan.md));
infrastructure as code (e.g. Terraform) is added once staging is actually set up.

## Images

| Image | Dockerfile target | Runs |
| --- | --- | --- |
| backend | `backend/Dockerfile` → `runtime` | API (default command), worker (`python -m app.jobs.worker`), migrations (`alembic upgrade head`) |
| web | `frontend/Dockerfile` → `runtime` | Next.js standalone server |

Both images run as non-root users, contain no build tooling, and define a `HEALTHCHECK`.
The backend image takes an `APP_VERSION` build argument (use the git SHA), which is
reported by `GET /api/v1/health`.

## Deploy order

1. Build and push images tagged with the git SHA.
2. Run the migration job once: `alembic upgrade head` with the new backend image.
   Migrations must be backwards compatible with the currently running version
   (expand → migrate → contract), because old API/worker containers keep running during
   the rollout.
3. Roll the `api` and `worker` services to the new image. Gate traffic on
   `GET /api/v1/health/ready`.
4. Roll the `web` service.

## Reference single-host layout

`docker-compose.prod.yml` at the repo root runs everything on one machine behind a TLS
reverse proxy:

```bash
cp infra/production.env.example infra/production.env   # fill in every value
docker compose -f docker-compose.prod.yml --env-file infra/production.env up -d --build
```

On a managed cloud, drop the `db` service and point `DATABASE_URL` at managed PostgreSQL 16
(with the `vector` extension allowed). No Redis is needed (ADR 0008).

## Health endpoints

| Endpoint | Use for |
| --- | --- |
| `GET /api/v1/health` | Liveness: the process is up. No dependency checks. |
| `GET /api/v1/health/ready` | Readiness / load-balancer gating: PostgreSQL and pgvector. Returns 503 with per-check detail on failure. |
| `GET /api/health` (web) | Web server liveness. |
| `JOBS_HEARTBEAT_FILE` age | Worker liveness: the worker touches the file every 10 s; the compose healthcheck fails if it is over 45 s old. |
| `POST /api/v1/admin/jobs/tick` | Scheduler entry point (`X-Jobs-Tick-Token`): enqueues due daily and hourly jobs. |
