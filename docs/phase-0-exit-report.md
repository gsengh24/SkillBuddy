# Phase 0 exit report

- **Date:** 2026-10-01
- **Audited:** `main` at `d6464c3` (merge of PR #7), plus PR #10 (Smoke and Secret scan jobs,
  open at the time of writing)
- **Verdict:** **Not ready for Phase 1.** See [Verdict](#verdict).

Statuses: **Pass**, **Fail**, or **Not verified** (could not be confirmed with the evidence
available). Every claim below cites the file, CI run or test it was checked against.

## Summary

| # | Exit criterion | Status |
| --- | --- | --- |
| 1 | `main` CI green (Backend, Frontend, Docker images, Smoke) | Not verified |
| 2 | `main` protected by a ruleset (PR-only, required checks) | Pass |
| 3 | Whole stack boots in CI (Smoke job) | Pass (on PR #10; not yet on `main`) |
| 4 | Migrations tested up and down against Postgres 16 | Pass |
| 5 | Authentication requirements | **Fail** |
| 6 | No secrets; debug off by default; `.env.example` complete | Pass |
| 7 | Docs complete and consistent | Pass (after three trivial fixes in this PR) |
| 8 | Evaluation-set skeleton validates; drafts clearly unreviewed | Pass |

## 1. `main` CI green: Not verified

- **Backend, Frontend, Docker images: green on `main`.** Run
  [36855255931](https://github.com/gsengh24/SkillBuddy/actions/runs/36855255931) on
  `d6464c3`: jobs
  [Backend](https://github.com/gsengh24/SkillBuddy/actions/runs/36855255931/job/110346122377),
  [Frontend](https://github.com/gsengh24/SkillBuddy/actions/runs/36855255931/job/110346122922)
  and [Docker images](https://github.com/gsengh24/SkillBuddy/actions/runs/36855255931/job/110346122702)
  all succeeded. Every earlier push run on `main` that was checked (`921ceff`, `67beaf5`,
  `ef9573a`) was also green.
- **Smoke is not on `main` yet.** It was added in PR #10 and has only run on that PR. Re-check
  this criterion on the first `main` run after PR #10 merges.

## 2. Ruleset on `main`: Pass

Read through the GitHub API (`GET /repos/gsengh24/SkillBuddy/rulesets/24301494`):

- Ruleset **"Protect main"**, enforcement **active**, target `~DEFAULT_BRANCH`, **no bypass
  actors**.
- Rules: `pull_request` (PR required; 0 approvals, which suits a solo owner), `deletion`,
  `non_fast_forward` (no force pushes), `required_status_checks`: **Backend, Frontend,
  Docker images** (GitHub Actions).
- Gaps: **Smoke** and **Secret scan** are not required yet (owner to add after PR #10), and
  "require branches to be up to date" is off. Classic branch protection is not used
  (`/branches/main/protection` returns 404); the ruleset replaces it.

## 3. Whole stack boots in CI: Pass (on PR #10)

PR #10 run [36856198984](https://github.com/gsengh24/SkillBuddy/actions/runs/36856198984),
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

## 5. Authentication: Fail

**The authentication module has not been built.** The auth task's own text was never
received in the working session, so this list uses the requirements named in the audit
request. The only auth code is a fail-closed stub.

| Requirement | Status | Evidence |
| --- | --- | --- |
| OTP rules (expiry, single use, attempt limit, hashed at rest) | Missing | No OTP model, endpoint or service exists |
| Session cookie flags (`HttpOnly`, `Secure`, `SameSite`) | Missing | No sessions |
| CSRF protection | Missing | No cookie-authenticated endpoints yet |
| Rate limits (OTP send, verify attempts) | Missing | No rate limiter |
| Email enumeration safety | Missing | No auth endpoints |
| Deletion grace period + scheduled hard delete | Missing | `users.deleted_at` column exists (`backend/app/models/user.py`); no deletion endpoint or job |
| Retention jobs (OTP/session purge, `auth_events` prune) | Missing | Planned in `docs/roadmap.md` |
| Text size limits on user input | Missing in the API | No user-text endpoints yet; the eval schema caps text at 2,000 chars (`test_profile_rejects_invalid_values`) |
| Security headers (API) | Implemented and tested | `SecurityHeadersMiddleware` in `backend/app/core/security.py`; `test_liveness_sets_security_headers` checks `X-Content-Type-Options` and `X-Frame-Options` (`Referrer-Policy`, `Cross-Origin-Opener-Policy` set but untested) |
| Security headers (web) | Implemented, untested | `frontend/next.config.ts` `headers()` |
| Protected endpoints fail closed until auth exists | Implemented and tested | `require_authenticated_user`; `test_auth_stub_fails_closed` |

ARCHITECTURE.md §11 lists an "auth skeleton" as a Phase 0 deliverable.

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

1. **No authentication or account lifecycle.** Phase 1 stores free-text profiles (personal
   data). Without auth, consent, rate limits and deletion, nothing user-facing can ship
   safely.
2. **No ground truth for match quality.** All 100 labels are unreviewed drafts; tuning the
   matcher against them would optimise towards guesses.
3. **Zero-cost AI may not fit free hosts.** Local CPU embeddings must run within 256-512 MB
   RAM hosts. There is no free always-on worker, and Arq polling would exhaust Upstash's
   500K commands/month in about 3 days.
4. **Staging is a plan, not a system.** Nothing has been deployed. Known prerequisites:
   API on `$PORT`, Neon URL scheme, a migration workflow. Open unknowns: Render Free with
   Docker, cold starts versus the 3-second status check.
5. **Free-tier limits and terms.** Neon blocks writes at 0.5 GB; storage rules and the size
   monitor do not exist yet. Vercel Hobby is non-commercial only. Actions minutes are free
   only while the repo is public.

## Prioritised issues (not fixed in this PR)

**Blockers for Phase 1**

1. Build the auth module to the requirements in §5 (or formally move it to Phase 1 with an
   ADR and update ARCHITECTURE.md §11). Either way, it is a prerequisite for storing real
   profiles.
2. Review the 100 draft evaluation labels (`backend/evals/data/pairs.json`) and mark them
   `reviewed`; rebalance `explore`.
3. Merge PR #10, add **Smoke** and **Secret scan** to the "Protect main" ruleset, and confirm
   the first green `main` run with all five jobs (criterion 1).

**High**

4. Phase 1 AI-gateway ADR: embedding model and dimension (make it a setting), no-LLM mode,
   memory budget on free hosts, how jobs run without a free worker.
5. Implement the storage rules before the first growing table: text caps, retention jobs,
   size monitor (`docs/roadmap.md`).
6. Staging prerequisites from `docs/deployment-plan.md`: API listens on `$PORT`, accept
   `postgresql://` URLs, "Migrate staging" workflow.
7. Exercise the Codespace once end to end; `.devcontainer/` has never been run.

**Medium**

8. Replace the Redis image with Valkey (licence), or record the decision to keep it.
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

**Not ready for Phase 1.** The engineering foundation is in good shape:
- CI runs lint, strict typing, migrations and 79 tests (95% coverage) on real Postgres 16 +
  pgvector and Redis.
- The full stack boots and passes smoke checks in CI.
- No secrets are in the history, and the docs are consistent.

What blocks Phase 1:

1. **Authentication is missing** (criterion 5 fails; ARCHITECTURE.md lists it for Phase 0).
2. **The evaluation set is unreviewed**, so there is no ground truth yet.
3. **Smoke is not yet on `main` or in the required checks** (criterion 1 not verified).

Item 3 needs only a merge and a ruleset change. Items 1 and 2 need real work, or (for
auth) an explicit decision to move it into Phase 1.
