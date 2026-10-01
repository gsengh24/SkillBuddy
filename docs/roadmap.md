# Roadmap: planned tasks

Task-level backlog that sits under the phases in
[ARCHITECTURE.md §11](ARCHITECTURE.md#11-phased-roadmap). Phases and their gates are defined
there; this file lists concrete work items that must not be forgotten when a phase starts.
Tick items off in the PR that delivers them.

## Scheduling note

Several items below are scheduled jobs (cron). Staging has no always-on worker
([ADR 0003](adr/0003-hosting.md)), so the scheduling mechanism is chosen in the Phase 1
AI-gateway/worker decision. Zero-cost fallback: a scheduled GitHub Actions workflow
(free for this public repository) that runs a small management command against the
database. Every job must be idempotent and safe to run late or twice.

## Authentication (auth module)

Storage tasks from [docs/storage-budget.md](storage-budget.md) and the storage rules in
CLAUDE.md:

- [ ] OTP codes and sessions tables carry an `expires_at` column with an index.
- [ ] Daily purge job: delete expired OTP codes and expired or revoked sessions.
- [ ] `auth_events` table with a fixed retention (number of days set in the ADR/PR) and a
      daily prune job.
- [ ] Account deletion: soft delete on request, then a scheduled hard-delete job that
      removes the user, profile, embeddings, matches and messages within 30 days
      (ARCHITECTURE.md §8).
- [ ] Input caps on all auth-related text fields (email length, etc.).
- [ ] PR states retention and estimated growth for each new table; rows added to
      `docs/storage-budget.md`.

## Phase 1: profiles, requests and the AI gateway

- [ ] Text caps enforced in request schemas: profile text and request text (2,000
      characters planned), with clear validation errors.
- [ ] Embedding dimension made a setting; 384 chosen in
      [ADR 0007](adr/0007-ai-gateway.md); migration 0003 adjusts `profile_embeddings` before
      any real data exists. The full Phase 1 AI build order is at the end of ADR 0007.
- [ ] AI gateway stores prompt version, tokens and latency only; raw prompts and responses
      kept at most for a short debug window (e.g. 7 days) and purged by a daily job.
- [ ] `events` table partitioned by month (ARCHITECTURE.md §5); raw events kept for a set
      window (30 days planned), then aggregated into daily counts and old partitions
      dropped by a scheduled job.
- [ ] **Size monitor:**
  - [ ] Database size (`pg_database_size`) and per-table sizes exposed on a protected
        admin/health endpoint.
  - [ ] Warning state at 70% of the plan limit (350 MB on Neon Free).
  - [ ] Protect mode at 90% (450 MB): new signups and non-essential writes paused, with a
        clear "try again later" error in the standard envelope.
  - [ ] Thresholds and the plan limit come from settings, not constants.
- [ ] Replace the estimates in `docs/storage-budget.md` with measured per-user sizes from
      staging (synthetic data).
