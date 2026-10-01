# 2. Modular monolith with a separate background worker

- **Status:** Accepted; the always-on Arq worker on Redis is superseded by
  [ADR 0008](0008-free-runtime-jobs-and-email.md) (Postgres job queue, run in the API process on free hosting or as
  a separate process when affordable). The API/worker module boundary still applies.
- **Date:** 2026-10-01

## Context

The platform has two very different kinds of work (see `docs/ARCHITECTURE.md`, sections 4
and 6):

1. **Request/response work**: profiles, requests, intros, connections, chat. Latency-sensitive,
   cheap, and mostly database reads and writes.
2. **AI work**: parsing free text into structure, computing embeddings, retrieval, ranking and
   LLM-written match explanations. Slow (seconds to tens of seconds), expensive, rate-limited
   by third-party providers, and prone to transient failure.

The team is one or two developers. Operating many services (separate deploys, network
contracts, distributed tracing, versioned internal APIs) would consume most of that capacity
before the product has users. At the same time, letting slow model calls run inside HTTP
requests would tie up API workers, make latency unpredictable, and couple user-facing
availability to model providers.

## Decision

Ship **one backend codebase with two process types**:

- **API** (FastAPI, `app.main:create_app`): handles HTTP. It never calls a language or
  embedding model. Anything that needs one is written to PostgreSQL and enqueued as a job,
  and the API returns immediately (clients poll or receive an event).
- **Worker** (Arq on Redis, `app.worker.settings.WorkerSettings`): executes background jobs,
  including all model calls through the single AI gateway module (added in Phase 1).

Both are built from the same image and share models, settings and services. Internally the
code is split into **modules with strict boundaries** (Auth, Profile, Request, Matching,
Connection, Messaging, Notification, Spaces, Admin/Trust). A module talks to another only
through that module's service functions, never by reaching into its tables or internals.

PostgreSQL (with pgvector) is the single source of truth; Redis is the job broker and cache.
Schema changes happen only through Alembic migrations, run as a separate one-shot step before
new API or worker versions start.

**Why Arq:** it is asyncio-native, like the API, so job code reuses the same async database
sessions and service functions without a sync/async split. It is small and easy to reason
about. Its trade-offs (fewer features than Celery, a smaller maintainer base) are acceptable
at this stage. If we need complex multi-step orchestration, Temporal is the documented next
step (`ARCHITECTURE.md`, section 10).

## Consequences

**Positive**

- One repository, one image, one deploy pipeline, one set of dependencies to patch.
- User-facing latency is independent of model latency; a provider outage degrades matching
  but not the rest of the product.
- API and worker scale independently (more worker replicas when the queue is deep).
- Refactoring across module boundaries is a normal code change, not a cross-service
  migration.

**Negative / risks**

- Module boundaries are enforced by convention and review, not by the network. Without
  discipline they erode. Mitigation: `CLAUDE.md` rules, review checklist, and (later) an
  import-linter contract in CI.
- A bug in shared code can affect both processes at once.
- Jobs must be idempotent: Arq retries failed jobs and may re-run a job after a worker crash.

**When to revisit**

Extract a module into its own service only when it needs independent scaling or deployment
cadence that the worker model cannot provide. `ARCHITECTURE.md` names the matcher as the
first candidate. Such a split requires a new ADR.
