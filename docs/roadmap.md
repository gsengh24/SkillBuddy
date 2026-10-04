# Roadmap: planned tasks

Task-level backlog that sits under the phases in
[ARCHITECTURE.md §11](ARCHITECTURE.md#11-phased-roadmap). Phases and their gates are defined
there; this file lists concrete work items that must not be forgotten when a phase starts.
Tick items off in the PR that delivers them.

## Scheduling note

Several items below are scheduled jobs (cron). Staging has no always-on worker
([ADR 0003](adr/0003-hosting.md)). [ADR 0008](adr/0008-free-runtime-jobs-and-email.md) settles it: a
PostgreSQL job queue run inside the API, woken by a Cloudflare Worker cron. Scheduled
GitHub Actions workflows were rejected (GitHub's terms forbid using Actions as part of a
serverless application). Every job must be idempotent and safe to run late or twice.

## Authentication (auth module)

Storage tasks from [docs/storage-budget.md](storage-budget.md) and the storage rules in
CLAUDE.md:

- [x] OTP codes and sessions tables carry an `expires_at` column with an index
      (`app/models/auth.py`; verified in step 8b).
- [x] Daily purge job: delete expired OTP codes and expired or revoked sessions
      (`purge_auth_data`, `app/services/auth/retention.py`).
- [x] `auth_events` table with a fixed retention (number of days set in the ADR/PR) and a
      daily prune job (`AUTH_EVENT_RETENTION_DAYS`, 90; in `purge_auth_data`).
- [x] Account deletion (`hard_delete_accounts` job; everything cascades): soft delete on
      request, then a scheduled hard-delete job that
      removes the user, profile, embeddings, matches and messages within 30 days
      (ARCHITECTURE.md §8).
- [x] Input caps on all auth-related text fields (email length, etc.; `EMAIL_MAX_LENGTH`
      254).
- [x] PR states retention and estimated growth for each new table; rows added to
      `docs/storage-budget.md`.

## Phase 1: profiles, requests and the AI gateway

- [x] Sign in with Google for `@thapar.edu` (ADR 0011), email codes kept as the fallback;
      allow-list, exceptions and block list for both methods.
- [x] Text caps enforced in request schemas (profile text 2,000 characters; request text
      1,000, `REQUEST_TEXT_MAX_LENGTH`, migration 0007): profile text and request text (2,000
      characters planned), with clear validation errors. Profile text: done (schema and
      CHECK, migration 0005); request text comes with the matching endpoints.
- [x] Profile API (`/api/v1/me/profile`): save with AI-consent version recorded, settings
      and visibility, user corrections of the parsed result; `parse_profile` job (AI or
      template, hash-cached) that queues the embedding; backfill for older profiles.
- [x] Match requests and the matcher (understand, retrieve by intent facet, rank in code,
      explain), `/api/v1/requests` endpoints, daily caps and retention (migration 0007).
- [x] Discover screen: intent chips, request box, request cards that wait for matches,
      match cards with the reason (no name before an intro).
- [x] Intros, connections and notifications API (migration 0008): two-sided consent,
      silent declines, names shared only on accept; intro emails within the Gmail quota.
- [x] Intro, connection and notification screens: send an intro from a match card,
      accept or decline on Notifications, connections on Messages, unread dot on the bell.
- [x] Profile onboarding and "About you" screens, with the ADR 0007 consent line, a
      review-and-correct step and a "show me in new matches" switch.
- [x] Embedding dimension made a setting; 384 chosen in
      [ADR 0007](adr/0007-ai-gateway.md); migration 0004 adjusts `profile_embeddings` before
      any real data exists. The full Phase 1 AI build order is at the end of ADR 0007.
- [x] Understand and Explain stages on the AI gateway, each with a template fallback
      that needs no AI (`app/ai/stages/`, prompts versioned in `app/ai/prompts/`); first
      quality check against the eval pairs (`evals/quality.py`).
- [x] AI gateway stores prompt version, tokens and latency only; raw prompts and responses
      kept at most for a short debug window (e.g. 7 days) and purged by a daily job.
      Verified in step 8b: no raw prompt or response is stored at all (metadata goes to the
      JSON logs and `match_requests.prompt_version`), so there is nothing to purge.
- [ ] (Not built: there is no `events` table yet; it comes with the feedback loop, not
      hardening.) `events` table partitioned by month (ARCHITECTURE.md §5); raw events kept for a set
      window (30 days planned), then aggregated into daily counts and old partitions
      dropped by a scheduled job.
- [x] **Size monitor** (`app/services/storage.py`, `GET /api/v1/admin/storage`):
  - [x] Database size (`pg_database_size`) and per-table sizes exposed on a protected
        admin/health endpoint.
  - [x] Warning state at 70% of the plan limit (350 MB on Neon Free).
  - [x] Protect mode at 90% (450 MB): new signups and non-essential writes paused, with a
        clear "try again later" error in the standard envelope.
  - [x] Thresholds and the plan limit come from settings, not constants
        (`DATABASE_SIZE_LIMIT_MB`, `STORAGE_WARN_PERCENT`, `STORAGE_PAUSE_PERCENT`).
- [ ] Replace the estimates in `docs/storage-budget.md` with measured per-user sizes from
      staging (synthetic data). Needs a synthetic load on staging first; not in step 8.

## Phase 3: chat and safety

- [x] **Chat** ([ADR 0012](adr/0012-chat-delivery-by-polling.md), migration 0009): messages only
      inside an accepted connection; only the two people can read them; read tracking and
      unread counts; adaptive polling with per-person and daily caps; messages deleted after
      90 days (`MESSAGE_RETENTION_DAYS`), with a note in the chat.
- [x] **Reports** (migration 0010; merged only after owner review): `POST /messages/{id}/report` with
      `REPORTS_PER_DAY`, a frozen copy of the reported message and the 10 before it, the
      admin reports API (`X-Admin-Token`, rate-limited, never logged; steps in
      [moderation.md](moderation.md)), and at most one alert email an hour with counts only;
      resolved reports deleted after 180 days.
- [x] **Report button and reasons** (step 7b, migration 0012): report a chat message,
      a received intro (`POST /intros/{id}/report`) or a profile (`POST /people/{id}/report`)
      with six reasons in plain words; the form says what the moderator will see, then
      offers to block. Reports now carry `target` and `target_id`.
- [x] **Blocking** (step 7a, migration 0011): block from a chat, a connection card or a
      received intro. It works both ways: no chat (`app/services/blocks.blocked_with`),
      the connection ends for good (`connections.ended_at`) and leaves both Messages lists,
      open intros are withdrawn and no new ones can be sent, and each is removed from the
      other's matches (hard filter in retrieval, and in match lists already shown). The
      blocked person isn't told; reporting still works. Unblock in Settings → Blocked
      people removes the block only; the old connection stays ended. `BLOCKS_PER_DAY` (20).
- [x] **Moderation page** (step 7c, migration 0013): `/moderation` for accounts in
      `MODERATOR_EMAILS` (normal sign-in, `is_moderator` on `/auth/me`); open and resolved
      reports with their copies; resolve, suspend (signs them out at once) and unsuspend;
      suspended accounts list; audit log of every action kept a year;
      `MODERATION_REQUESTS_PER_MINUTE` (60). API under `/api/v1/moderation`.
- [x] **Privacy and terms rewrite** (step 7d; still drafts until legal review): what we
      collect, `/privacy#ai` (ADR 0007 §5 wording), who sees what, chat (90 days, no AI),
      reports and their copies (180 days after resolve, kept past account deletion), blocks,
      moderation, emails, a retention list, services used and rights; terms with conduct
      rules, blocking and moderation. `TERMS_VERSION` 2026-10-04-draft. The placeholder
      contact address lives in `frontend/lib/legal.ts` (pre-launch checklist item 43).
- [x] **Email switch** (step 7d): Account settings, Emails, "Emails about intros" (on by
      default); intro emails now point there.
- [ ] Automated screening of messages: not in chat v1; decide in item 7 (it would send
      message text to an AI provider, which needs consent and privacy wording).

## Phase 5: pair spaces ([ADR 0013](adr/0013-pair-spaces-v1.md))

- [ ] **Backend (step 9b):** goals, skills to grow and progress logs on each open
      connection; limits; block hook; space deleted 90 days after the connection ends;
      logs deleted 90 days after writing.
- [ ] **Web (step 9c):** the Pair spaces page, and the nav item switched on.
- [ ] **Reporting goal titles and log notes (step 9d, owner review):** report targets
      `goal` and `progress_log`, and the privacy page's retention lines for spaces.
- [ ] **Post-launch:** reminders (in-app, maybe email within the non-login budget).
- [ ] **Post-launch:** conversation starters and project templates.

## Hardening

- [x] **Staging migration drift check** (step 8a; `.github/workflows/staging-migrations.yml`,
      `app/db/drift.py`): a check that fails or warns when the staging
      database is behind the migrations in `main` (for example, `alembic current` against
      Neon compared with the newest file in `backend/migrations/versions/`, run after every
      merge to `main`). Migrations on staging are applied by hand ("Migrate staging"), and
      on 2026-10-02 0007 and 0008 were missed: the API read a column that did not exist and
      every signed-in page returned 500 until the workflow was run.
