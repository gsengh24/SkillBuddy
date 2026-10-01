# Phase 0 exit report

- **Date:** 2026-10-01
- **Audited:** `main` at `d6464c3` (merge of PR #7), plus PR #10 (Smoke and Secret scan jobs,
  open at the time of writing)
- **Re-audited:** criteria 1, 2, 3 and 5 later the same day, against `main` at `975a1eb`
  (merge of PR #10) and the open authentication PRs #12 (backend), #13 (email and jobs) and
  #14 (frontend), which are stacked and merge in that order
- **Verdict:** **Not ready for Phase 1** until the auth PRs are merged and the evaluation
  labels are reviewed. See [Verdict](#verdict).

Statuses: **Pass**, **Fail**, or **Not verified** (could not be confirmed with the evidence
available). Every claim below cites the file, CI run or test it was checked against.

## Summary

| # | Exit criterion | Status |
| --- | --- | --- |
| 1 | `main` CI green (Backend, Frontend, Docker images, Smoke) | Pass |
| 2 | `main` protected by a ruleset (PR-only, required checks) | Pass |
| 3 | Whole stack boots in CI (Smoke job) | Pass |
| 4 | Migrations tested up and down against Postgres 16 | Pass |
| 5 | Authentication requirements | **Pass on PRs #12-#14; not yet on `main`** |
| 6 | No secrets; debug off by default; `.env.example` complete | Pass |
| 7 | Docs complete and consistent | Pass (after three trivial fixes in this PR) |
| 8 | Evaluation-set skeleton validates; drafts clearly unreviewed | Pass |

## 1. `main` CI green: Pass

- Re-audit: `main` run
  [36858444007](https://github.com/gsengh24/SkillBuddy/actions/runs/36858444007) on `975a1eb`
  (merge of PR #10): **Backend, Frontend, Docker images, Smoke, Secret scan** all succeeded.
- First audit: run 36855255931 on `d6464c3` had Backend, Frontend and Docker images green;
  Smoke did not exist on `main` yet.

## 2. Ruleset on `main`: Pass

Read through the GitHub API (`GET /repos/gsengh24/SkillBuddy/rulesets/24301494`):

- Ruleset **"Protect main"**, enforcement **active**, target `~DEFAULT_BRANCH`, **no bypass
  actors**.
- Rules: `pull_request` (PR required; 0 approvals, which suits a solo owner), `deletion`,
  `non_fast_forward` (no force pushes), `required_status_checks`: **Backend, Frontend,
  Docker images, Smoke, Secret scan** (re-audit; the first audit found only the first three).
- Remaining gap: "require branches to be up to date" is off. Classic branch protection is
  not used (`/branches/main/protection` returns 404); the ruleset replaces it.

## 3. Whole stack boots in CI: Pass

Also green on `main` (run 36858444007). PR #10 run [36856198984](https://github.com/gsengh24/SkillBuddy/actions/runs/36856198984),
job **Smoke** (1m17s), script `.github/scripts/smoke.sh`:

- `docker compose up --build --detach --wait`: db, redis, api, worker, web **Healthy**;
  migrate **Exited** (0).
- Readiness: `{"status":"ok","checks":{"database":ok,"pgvector":ok,"redis":ok}}`.
- "web page: API connected" (`data-state="connected"` on port 3000).
- "worker: ping job returned pong" (job enqueued through Redis, executed by the Arq worker).
- "alembic current: 0001 (head)"; the three Phase 0 tables exist.

Not yet seen: the job failing correctly when a service is broken.

## 4. Migrations up and down on Postgres 16: Pass

`main` run 36855255931, job Backend, service image `pgvector/pgvector:0.8.6-pg16-trixie`:

- Step **"Migrations (upgrade, downgrade, re-upgrade, drift check)"** (`.github/workflows/ci.yml`):
  log shows `Running upgrade -> 0001`, `Running downgrade 0001 ->`, `Running upgrade -> 0001`,
  then `alembic check` passed.
- Tests (in `backend/tests/integration/test_migrations.py`, both passed):
  `test_upgrade_downgrade_upgrade` (tables, `vector`/`citext` extensions and the HNSW
  index appear, disappear, reappear) and `test_models_and_migrations_are_in_sync`.
- Also passing against the same database: `tests/integration/test_models_db.py` (6 tests:
  defaults, case-insensitive email, cosine ordering, unique and check constraints, cascade
  delete). Overall: 79 passed, coverage 95.38% (threshold 85%).

## 5. Authentication: Pass on PRs #12-#14 (not yet on `main`)

Re-audit. Built in three stacked PRs, each green on all five CI jobs. Design and decisions:
[ADR 0006](adr/0006-authentication-and-sessions.md) (auth, sessions, CSRF) and
[ADR 0005](adr/0005-valkey-instead-of-redis.md) (Valkey); both ADRs are added by PR #12. The
first audit's result was **Fail** (nothing built).

| PR | CI run | Result |
| --- | --- | --- |
| #12 backend | [36881647505](https://github.com/gsengh24/SkillBuddy/actions/runs/36881647505) | 5/5 jobs; 136 backend tests; auth modules 99% coverage (gate at least 90%) |
| #13 email and jobs | [36883330720](https://github.com/gsengh24/SkillBuddy/actions/runs/36883330720) | 5/5 jobs; 165 backend tests; smoke signs in with a code emailed via Mailpit |
| #14 frontend | [36887713990](https://github.com/gsengh24/SkillBuddy/actions/runs/36887713990) | 5/5 jobs; 27 component tests; Playwright sign-up and sign-out test passed |

Test files: `backend/tests/integration/test_auth_codes.py`, `test_auth_sessions.py`,
`test_retention.py`, `test_storage_guard.py`, `test_email_delivery.py`, `test_migrations.py`;
`frontend/components/auth/*.test.tsx`; `frontend/e2e/tests/login.spec.ts`.

| Requirement | Status | Evidence (tests) |
| --- | --- | --- |
| OTP: 6 digits, 10-minute expiry | Implemented and tested | `test_code_expires_after_ten_minutes`, `test_expired_code_is_rejected`, `test_code_must_be_six_digits` |
| OTP: wrong code, 5-attempt lockout | Implemented and tested | `test_wrong_code_is_rejected_and_five_attempts_lock_the_code` |
| OTP: single use; a new request invalidates the old code | Implemented and tested | `test_code_is_single_use`, `test_new_request_invalidates_the_previous_code` |
| OTP: stored only as an HMAC; constant-time comparison | Storage tested; comparison by code review | `test_codes_are_stored_only_as_hmac`; `constant_time_equals` in `app/services/auth/service.py` |
| Age 18+ and terms required for new accounts | Implemented and tested | `test_new_account_requires_age_and_terms_and_keeps_code_usable`; login-form component tests |
| Session cookie flags (HttpOnly, Secure, SameSite=Lax, 90-day Max-Age) | Implemented and tested | `test_session_and_csrf_cookie_flags`, `test_cookie_is_not_secure_on_the_plain_http_dev_stack`; e2e cookie assertions |
| Session expiry (30-day sliding, 90-day absolute) and revocation | Implemented and tested | `test_expired_session_is_rejected_and_removed`, `test_activity_slides_the_idle_expiry`, `test_sliding_never_passes_the_absolute_maximum`, `test_logout_revokes_the_session_and_clears_cookies`, `test_logout_all_revokes_every_session` |
| CSRF (signed double-submit) | Implemented and tested | `test_cookie_authenticated_writes_require_the_csrf_token` (missing, empty, wrong), `test_csrf_token_from_another_session_is_rejected`, `test_bearer_clients_do_not_need_csrf`; `account-actions.test.tsx` sends the header; e2e signs out through it |
| Rate limits per email and per IP, 429 with Retry-After | Implemented and tested | `test_code_requests_are_rate_limited_per_email`, `test_code_requests_are_rate_limited_per_ip`, `test_verification_is_rate_limited`, `test_rate_limiter_fails_closed_when_valkey_is_down` |
| Email enumeration safety | Implemented and tested | `test_request_response_is_identical_for_known_and_unknown_addresses`; also for accounts pending deletion (`test_delete_account_starts_the_grace_period_and_refuses_sign_in`) |
| Deletion: 30-day grace period, sign-in refused with a clear message | Implemented and tested | `test_delete_account_starts_the_grace_period_and_refuses_sign_in`; settings component test of the confirmation |
| Hard-delete job after the grace period (cascade plus audit event) | Implemented and tested | `test_hard_delete_removes_due_accounts_with_all_their_rows`; schedule in `test_daily_retention_jobs_are_scheduled` |
| Retention jobs (expired codes and sessions; auth_events after 90 days) | Implemented and tested | `test_purge_removes_expired_codes_sessions_and_old_events` |
| Security headers (API) | Implemented and tested | `test_liveness_sets_security_headers`, `test_responses_are_not_cacheable`, `test_deployed_environments_send_hsts` |
| Security headers (web) | Implemented, untested | `frontend/next.config.ts` `headers()` |
| Text size limits | Implemented; mostly tested | email at most 254 characters and JSON-only bodies (`test_request_rejects_invalid_input`, `test_endpoints_require_a_json_body`); user-agent and IP truncation not tested directly |
| Never log codes, tokens or full emails | Implemented and tested | `test_codes_tokens_and_addresses_are_never_logged`, `test_send_login_code_emails_the_code_but_never_logs_it` |
| Append-only audit log | Implemented and tested | `test_auth_events_are_append_only` |
| Migration up and down | Implemented and tested | `test_auth_migration_downgrades_to_0001_and_back`; the CI migration step |
| Storage guard (warn at 70%, pause sign-ups at 90%) | Implemented and tested | `test_near_the_limit_new_signups_pause_but_existing_users_sign_in`, `test_optional_writes_are_refused_near_the_limit` |

**Why not Pass outright:** none of #12-#14 is merged, so `main` has no auth yet. Re-check the
first `main` run after #14 merges (all five jobs, including the Playwright test in Smoke).

## 6. Secrets, debug mode, env examples: Pass

- **No secrets in history:** PR #10 job **Secret scan** ran gitleaks 8.30.1 (release checksum
  verified) over the full history: "22 commits scanned", **"no leaks found"**.
- **`.env` files ignored:** same job, `.github/scripts/check-env-ignored.sh`: ".env files are
  ignored; only *.example files are tracked."
- **Debug off by default:** `debug: bool = False` in `backend/app/core/config.py`;
  `DEBUG=false` in `backend/.env.example`; neither Compose file sets `DEBUG`; production
  refuses `DEBUG=true`, `*` CORS and `DB_ECHO` (`test_production_rejects_unsafe_options`,
  `test_defaults_are_safe`).
- **Examples complete** (scripted comparison): every `Settings` field is in
  `backend/.env.example` and nothing extra; `frontend/lib/env.ts` vars are in
  `frontend/.env.example`; every `${VAR}` in `docker-compose.yml` is in `.env.example`, and
  every one in `docker-compose.prod.yml` is in `infra/production.env.example`.
- Minor: `docker-compose.yml` sets `NEXT_PUBLIC_API_URL` for the web service but no frontend
  code reads it (listed below; not fixed here because it is configuration).

## 7. Docs complete and consistent: Pass

Checked: README.md, CLAUDE.md, CONTRIBUTING.md, `docs/adr/0001`-`0004`,
`docs/free-tier-limits.md`, `docs/storage-budget.md`, `docs/deployment-plan.md`,
`docs/roadmap.md`, `infra/README.md`, `backend/evals/README.md`.

- **ADR numbering:** 0001, 0002, 0003, 0004: sequential, titles match file names, all
  "Accepted".
- **Links:** scripted check of every relative Markdown link: none broken.
- **Trivial fixes made in this PR:**
  1. README "Develop in Codespaces" step 2: garbled sentence about what post-create installs.
  2. README "Quick start": now says it is for machines with Docker, not the owner's laptop,
     matching "How we work".
  3. `infra/README.md`: still said Terraform waits for "the hosting decision"; now points
     to ADR 0003 and the deployment plan.
- **Known drift, not a docs bug:** ARCHITECTURE.md §11 still lists Phase 0 deliverables that
  were deferred or are incomplete (staging environment, auth skeleton). ADR 0003 records
  the staging change; auth has no record (see blockers).

## 8. Evaluation set: Pass

- `backend/evals/` (schema, 40 profiles, 100 pairs, runner, README).
- `main` run 36855255931, job Backend: `tests/unit/test_evals.py` **25 passed**, including
  `test_committed_dataset_is_valid_and_complete`,
  `test_committed_pairs_are_all_unreviewed_drafts`,
  `test_committed_labels_are_roughly_balanced`, `test_every_profile_appears_in_a_pair`,
  `test_runner_prints_counts_per_intent_and_label` and `test_runner_fails_on_invalid_data`.
- Drafts are clearly unreviewed: every pair has `"review_status": "draft"` (enforced by
  the test above), and `backend/evals/README.md` opens with a callout saying the labels are
  not ground truth until reviewed.
- Labels: 32 good, 35 acceptable, 33 poor; `explore` skews good (9 of 16).

## Zero-cost constraint check (ADR 0004)

No violations found: no paid service, paid-only dependency or card requirement in the
repository, CI or dev setup. Points to watch:

- CI is free only while the repository is **public** (`docs/free-tier-limits.md`). Smoke adds
  about 1.5 minutes per run.
- `docker-compose.prod.yml` (reference single-host layout) and the optional ~$7/month worker in
  `docs/deployment-plan.md` would cost money if used; both are documented as not adopted.
- Rule 3 (configurable embedding dimension) is **not yet met**: `EMBEDDING_DIMENSIONS = 768`
  is a constant in `backend/app/models/profile_embedding.py`, scheduled for the Phase 1
  AI-gateway ADR.

## Licences

Scanned all 64 locked Python packages (PyPI metadata) and all npm packages in
`frontend/package-lock.json`.

| Component | Licence | Concern |
| --- | --- | --- |
| `redis:7.4-alpine` image (dev, CI, reference prod) | RSALv2 / SSPLv1 (source-available, not OSI open source) | **Restrictive.** Fine for internal use; conflicts with an "open-source only" reading of ADR 0004. Valkey (BSD-3-Clause) is a drop-in alternative. |
| `psycopg`, `psycopg-binary`, `psycopg-pool` (runtime) | LGPL-3.0-only | Weak copyleft; OK as an unmodified library. Ship licence notices if images are distributed. |
| `@img/sharp-libvips-*` via Next.js image optimisation (runtime, optional) | LGPL-3.0-or-later | Same as above; the app does not use `next/image`. |
| `lightningcss`, `axe-core` (build/dev only) | MPL-2.0 | File-level copyleft, dev tooling only: no concern. |
| `mypy-extensions` (dev) | No licence metadata on PyPI | MIT upstream; metadata gap only. |

Everything else is MIT, BSD, Apache-2.0, ISC, PSF or similar permissive licences. The project
itself is proprietary (`LICENSE`).

## Top 5 risks before Phase 1

1. **Auth is built but not merged.** PRs #12-#14 must merge in order; until then `main` has
   no sign-in. Real email for staging (a free SMTP relay) is still to be chosen.
2. **No ground truth for match quality.** All 100 labels are unreviewed drafts; tuning the
   matcher against them would optimise towards guesses.
3. **Zero-cost AI may not fit free hosts.** Local CPU embeddings must run within 256-512 MB
   RAM hosts. There is no free always-on worker, and Arq polling would exhaust Upstash's
   500K commands/month in about 3 days.
4. **Staging is a plan, not a system.** Nothing has been deployed. Known prerequisites:
   API on `$PORT`, Neon URL scheme, a migration workflow. Open unknowns: Render Free with
   Docker, cold starts versus the 3-second status check.
5. **Free-tier limits and terms.** Neon blocks writes at 0.5 GB (the size monitor and the 90%
   sign-up pause arrive with PR #13). Vercel Hobby is non-commercial only. Actions minutes are
   free only while the repo is public.

## Prioritised issues (not fixed in this PR)

**Blockers for Phase 1**

1. ~~Build the auth module~~: done in PRs #12-#14 (re-audit). **Merge them in order** and
   confirm the first green `main` run.
2. Review the 100 draft evaluation labels (`backend/evals/data/pairs.json`) and mark them
   `reviewed`; rebalance `explore`.
3. ~~Merge PR #10 and require Smoke and Secret scan~~: done (re-audit, criteria 1 and 2).

**High**

4. Phase 1 AI-gateway ADR: embedding model and dimension (make it a setting), no-LLM mode,
   memory budget on free hosts, how jobs run without a free worker.
5. ~~Storage rules for the auth tables~~: done in #12 and #13 (caps, retention jobs, size
   monitor). Profile and request text caps follow in Phase 1.
6. Staging prerequisites from `docs/deployment-plan.md`: API listens on `$PORT`, accept
   `postgresql://` URLs, "Migrate staging" workflow.
7. Exercise the Codespace once end to end; `.devcontainer/` has never been run.

**Medium**

8. ~~Replace the Redis image with Valkey~~: done in #12 (ADR 0005).
9. Commit an exported OpenAPI spec (ARCHITECTURE.md lists "OpenAPI spec" for Phase 0);
   today it exists only at runtime (`/openapi.json`, health endpoints only).
10. Prove the Smoke job fails correctly (e.g. a throwaway PR that breaks readiness).
11. Confirm the next weekly Dependabot `uv` run succeeds after the redis cap.
12. Consider requiring branches to be up to date in the ruleset.

**Low**

13. Remove the unused `NEXT_PUBLIC_API_URL` from `docker-compose.yml`.
14. Arq's internal call to the deprecated redis `close()` produces a test warning
    (`tests/integration/test_worker_queue.py::test_ping_job_round_trip`); upstream issue,
    no action needed now.
15. Add a third-party notices file before distributing images (LGPL components).

## Verdict

**Not ready for Phase 1 yet, but close.** Re-audit status:
- CI on `main` is green on all five required jobs.
- `main` is protected by a ruleset that requires them.
- The whole stack boots and passes smoke checks.
- Authentication is complete and tested on the PR stack: 165 backend tests (auth modules at
  99% coverage), 27 component tests, and a Playwright end-to-end sign-in.

What still blocks Phase 1:

1. **Merge the auth PRs #12, then #13, then #14**, and confirm the first `main` run is green
   on all five jobs (criterion 5 then passes on `main`).
2. **Review the 100 draft evaluation labels**, so the matcher has ground truth.

The first audit's verdict (same day) listed authentication as missing; that is resolved,
pending merge.
