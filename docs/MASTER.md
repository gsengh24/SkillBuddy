# Cynergi: master file

A single, from-scratch description of the whole project as it stands in `main`
(last product merge: PR #151, 2026-10-12; written 2026-11-10).

**Current phase: end of Phase 3, before the closed beta.** Phases 0–3 are built except the
evaluation run in CI (Phase 2) and automated screening (Phase 3); pair spaces v1 (Phase 5)
and teams (5b) are built too. Staging is live with no real users. Phase 4 has not started. It summarises; the detailed
sources are linked in each section. Where this file and a source disagree, the source wins:
`docs/ARCHITECTURE.md` for scope, `docs/adr/` for decisions, the code for behaviour.

---

## 1. What Cynergi is

An **AI matchmaking platform for people**: collaborators, skill partners and interest
buddies. Not dating, not jobs, not a marketplace, not a social feed.

- You describe yourself in free text. An LLM extracts structure (skills, interests, goals,
  availability, what you offer, what you seek).
- You ask for something ("a designer for my budgeting app"). The matcher finds a few people
  and explains each match in one or two sentences.
- **Two-sided consent:** nobody can message you until you accept their intro. Names are
  shared only after acceptance.
- After connecting: one-to-one chat, and **pair spaces** (groups of up to six with a chat,
  shared goals, skills to grow and progress notes).

**Formerly "Skill Buddy"**, renamed to Cynergi in October 2026 ([rename.md](rename.md)).
Internal identifiers use the neutral name `matchmaking`; real hosted resources keep their
old `skill-buddy` names.

**First audience:** one college, Thapar Institute of Engineering & Technology
(`@thapar.edu`). Adults only (18+, self-declared).

**People** (from the static `/team` page): Gaganjot Singh (builder/owner); Dr Prashant
Singh Rana (mentor, Associate Professor, Thapar); Gurvar Singh Gulati (contributor,
frontend and design); Namanmeet Singh (contributor). Most code is written by Claude Code
through PRs that the owner reviews or allows to auto-merge.

### The six intents

Every match request has one intent, and the intent decides what the matcher searches.

| Intent | Example | Search |
| --- | --- | --- |
| `build_together` | "Building a budgeting app, need a designer" | my *seek* vs their *offer*, scored both ways |
| `skill_exchange` | "Teach Python, learn guitar" | seek vs offer, reciprocity weighted equally |
| `mentor` | "Guidance moving from sales to product" | seek vs offer, one-sided |
| `interest_buddy` | "Someone to read medieval history with" | interest vs interest |
| `accountability` | "Keep me consistent on my startup" | identity vs identity |
| `explore` | "Show me interesting people" | identity, plus diversity (MMR) |

---

## 2. Hard constraints that shape everything

1. **Zero cost** ([ADR 0004](adr/0004-zero-cost-constraint.md)). Free tiers or open source
   only, no credit card on any account. Every limited resource has a hard cap and fails
   with "try again later", never a bill or a crash. Free-tier limits are recorded, dated,
   in [free-tier-limits.md](free-tier-limits.md).
2. **Storage budget** ([storage-budget.md](storage-budget.md)). Neon Free gives 0.5 GB; the
   budget is 70% (350 MB). At 70% admins are warned; at 90% signups and non-essential writes
   pause (`require_storage_capacity`). Every user-written field has a length cap. No uploads.
   Every growing table ships with a retention rule. Estimate: ~163 KB per user.
3. **The laptop never runs the app.** No Docker or Postgres locally. GitHub Actions CI is
   the test runner; staging is where the app is seen; Codespaces can run the full stack.
4. **Privacy by default.** Raw LLM prompts and responses are never stored. Only redacted
   text and alias-labelled summaries go to AI providers, and only to providers whose terms
   forbid training on inputs. Embeddings count as personal data.
5. **Frontend-agnostic API.** Versioned REST under `/api/v1`, OpenAPI is the contract
   (committed at `docs/api/openapi.json`, CI fails when stale), one error envelope,
   bearer tokens work as well as cookies. A mobile app may come later.

---

## 3. Architecture

```
Browser ──► Next.js web app (Vercel Hobby)
              │  same-origin /api/v1/* forwarder (cookies stay first-party)
              ▼
           FastAPI API (Render Free, Docker, Singapore; sleeps when idle)
              │  writes rows + enqueues jobs, never calls a model
              ▼
           PostgreSQL 16 + pgvector (Neon Free, Singapore, capped at 0.25 CU)
              data, embeddings, job queue, rate-limit counters, AI-cap counters
              ▲
           Job runner (inside the API when JOBS_RUN_IN_API=true; separate worker in dev/CI)
              ├─► AI gateway ─► Groq (primary) / Cloudflare Workers AI (secondary)
              │              └► bge-small-en-v1.5 embeddings, local CPU (fastembed/ONNX)
              └─► Gmail API (sign-in codes, intro emails, alerts; 450/day cap)

Cloudflare Worker cron ──► POST /api/v1/admin/jobs/tick (enqueues due daily/hourly jobs)
UptimeRobot ──► GET /ping (keep-alive)
```

- **Modular monolith + jobs** ([ADR 0002](adr/0002-modular-monolith-with-worker.md),
  [ADR 0008](adr/0008-free-runtime-jobs-and-email.md)). One codebase, one image. Modules
  talk only through each other's service functions.
- **No Redis/Valkey anywhere** (ADR 0008 superseded [ADR 0005](adr/0005-valkey-instead-of-redis.md)).
  Queue = `jobs` table with `FOR UPDATE SKIP LOCKED`, leases, exponential backoff, `dead`
  after max attempts. The runner does no idle polling (start-up, in-process enqueue signal,
  next `run_at`, or a tick). AI jobs run one at a time (RAM); I/O jobs two at a time.
- **Login codes are never stored in the job table**: kept in process memory keyed by job
  id; if the process dies, the job ends "expired unsent".
- **Scheduler:** Cloudflare Worker `skill-buddy-tick` (`infra/cloudflare-tick/worker.js`),
  17 ticks a day (hourly 08:00–23:00 IST, plus 06:00 IST). Each tick enqueues jobs keyed by
  period, so late, missed or repeated ticks neither skip nor duplicate work.
- **Migrations** run as a separate one-shot step, never at API start. On staging, via the
  "Migrate staging" GitHub workflow; a drift check (`staging-migrations.yml`,
  `app/db/drift.py`) fails when staging is behind `main`.

### Chat delivery ([ADR 0012](adr/0012-chat-delivery-by-polling.md))

No WebSockets/SSE (free hosts sleep; Vercel can't hold sockets). REST + adaptive client
polling: 3 s for 60 s after activity → 10 s → 30 s → **stop** after 10 quiet minutes,
resume on focus/typing. No polling in hidden tabs. One poll endpoint
(`GET /messages/updates`) covers one-to-one and team chats. Caps: `CHAT_POLLS_PER_MINUTE`
(40) per user, `CHAT_POLLS_PER_DAY` (16,000) global, sized to half of Vercel's monthly
invocations; over the cap → 429 and the client drops to one poll a minute.

---

## 4. The matching engine

Code: `backend/app/services/matching/engine.py`, `app/ai/`. Runs only in the
`match_request` job.

1. **Understand** (`app/ai/stages/understand.py`, prompt `understand_v2`). LLM turns profile
   or request text into structured JSON. It writes the platform's own wording (heading,
   sentence, tags) because that is what *other* people see; a person's own words are shown
   only to them. Template fallback with no AI. Profile parses are hash-cached.
2. **Retrieve (hybrid).** The request is embedded once and compared to one facet of every
   matchable profile (facets: identity, offer, seek, interest; 384-dim, `model_version` on
   every row). A keyword search on word stems runs alongside. Hard filters: not self, active
   accounts only, "show me in new matches" on, current-model vectors, blocks both ways,
   team members excluded for team requests. Up to 60 candidates.
3. **Rank (in code, never by the model).**
   `relevance = rescaled two-sided fit + 0.25 × keyword`;
   `score = relevance × (1 − inactivity − seen − overexposure)`.
   Fit is rescaled from cosine 0.45–0.75 to 0–1 (bge cosines sit in a narrow band).
   Penalties take a share of relevance, so they order close candidates but never lift a
   poor fit. Hand-set weights per intent (`WEIGHTS`). `explore` uses MMR (λ 0.7).
   **Quality floor:** relevance below `MATCH_MIN_RELEVANCE` (0.3) is dropped.
4. **Explain / judge** (`explain.py`, prompt `explain_v3`). The top 15, anonymised, go to
   the LLM with the requester's own parsed profile. The LLM fills a rubric per candidate
   (fits the ask, what else they share, any contradiction) and writes reasons. **Code**
   turns the rubric into a score, drops anyone under `MATCH_MIN_JUDGE_SCORE` (0.4) or with a
   contradiction, and keeps up to `MATCHES_PER_REQUEST` (5). Fewer matches, or none
   ("waiting for a match"), beats weak ones. Template fallback keeps the top of the ranking.

**AI gateway** ([ADR 0007](adr/0007-ai-gateway.md)): the only place models are called.
LLM-first by default; the rule-based/template path is a fallback when caps run out,
providers fail or `AI_LLM_ENABLED=false`. Providers: Groq (`gpt-oss-120b` for selection,
`gpt-oss-20b` for parsing, a spill-over model) with Zero Data Retention on; Cloudflare
Workers AI `@cf/openai/gpt-oss-20b` second. 20 s timeout; daily caps per user
(`AI_USER_DAILY_MATCH_REQUESTS` 3, `AI_USER_DAILY_UNDERSTAND_CALLS` 5), global
(`AI_LLM_DAILY_CALL_CAP` 400) and per provider (Groq 190k tokens, Cloudflare 9k neurons).
Outputs are Pydantic-validated with one retry. Only metadata is kept (`ai_calls`: provider,
kind, outcome, duration, cost; 30 days). Sized for roughly **200–500 daily active users**.
Embedding model must keep API + model under 400 MB RSS (CI checks it).

**Evaluation set** (`backend/evals/`): 40 synthetic profiles, ~100 labelled pairs across the
six intents. **All labels are still `draft` in `main`**; results must count only reviewed
pairs. Precision@5 for both the LLM and fallback paths has not been run yet.

**Skill suggestions** ([ADR 0020](adr/0020-skill-suggestions.md)): `GET /skills/suggest`
searches a bundled list (~930 names: O*NET Technology Skills + a curated list) in memory.
Suggest, don't force; tags stay plain strings.

---

## 5. Features as built (in `main`)

### Accounts and sign-in ([ADR 0006](adr/0006-authentication-and-sessions.md), [ADR 0011](adr/0011-google-sign-in.md), [ADR 0009](adr/0009-adults-only-self-declaration.md))
- **Email codes:** 6 digits, 10 minutes, 5 tries, stored only as an HMAC, sent by a job.
  Same response whether or not the account exists.
- **Google sign-in** (OIDC + PKCE, server-side), `@thapar.edu` only, off unless configured.
  Email codes remain the fallback.
- **Who may sign in:** `ALLOWED_EMAIL_DOMAINS`, `ALLOWED_EMAILS` (exceptions, email codes
  only), `BLOCKED_EMAILS`; plus admin-managed signup modes, domains, an invite-only
  application queue and invite codes (migration 0022).
- **18+ only**, by a required tick box (`users.age_confirmed_at`), plus terms acceptance
  with `terms_version`. No verification.
- **Sessions:** opaque 256-bit token, SHA-256 in the DB, httpOnly `session` cookie,
  30 days sliding / 90 absolute; `Authorization: Bearer` also accepted. **CSRF:** signed
  double-submit `csrf_token` cookie + `X-CSRF-Token` header on cookie-authenticated writes.
- Devices list, sign out one / others / all; **pause** and **resume** account;
  **delete** account (30-day grace, then hard delete with cascades); **"Download my data"**
  (gzipped JSON, emailed link valid 72 h, once per 24 h).
- Rate limits in Postgres fixed-window counters; `auth_events` append-only audit
  (trigger blocks UPDATE).

### Profile ("You" page)
- Free-text about (≤ 2,000 chars), display name, up to 3 links, availability fields, skill
  tags with suggestions; AI-consent version recorded on first save.
- Parsed result shown back for correction (`PUT /me/profile/understanding`).
- "Show me in new matches" switch; optional **Google account photo** (address only, Google
  hosts only, connections only, off by default; [ADR 0017](adr/0017-google-profile-photo.md)).
- Profile-completion nudge on Home.

### Requests, matches, intros, connections
- `POST /requests` (≤ 1,000 chars), 10/day, max 5 open, expire after 30 days, kept 90.
- Match cards show the reason, never the name, before an intro.
- **Intros:** note ≤ 500 chars, 10/day, 20 pending max, expire after 14 days. Declines are
  silent (looks pending until expiry). Accept → **connection**, names shared.
- In-app **notifications** (90 days) and intro **emails** (switchable in Settings → Emails).

### Chat
- Only inside an open connection; read state and unread counts; 300 messages/day;
  messages deleted after 90 days (shown in the chat). "Staying safe" tips until 10 messages.
  Enter to send.

### Pair spaces (= teams) ([ADR 0016](adr/0016-teams.md), [ADR 0018](adr/0018-pair-spaces-are-teams.md))
- User-facing name "pair space"; code, tables and API say `teams`. `/spaces` redirects to
  `/teams`. The older one-to-one spaces were removed (migration 0034).
- Up to 6 people; a person is in ≤ 5 and owns ≤ 3. One owner (passes to the
  longest-standing member on leave); last one out closes it.
- **Four ways in**, each needing the joiner's own action: owner invites a connection;
  invite link (7 days, resettable, joins at once); listed teams + "ask to join" (silent
  decline); the **matcher finds teammates** (a match request with `team_id`; "Invite to
  team" instead of "Send intro").
- Team chat (same poll, same message caps), shared goals (≤ 30), skills to grow (≤ 10 per
  person), progress notes (≤ 500 chars, deleted after 90 days); 100 space writes/day.
- Blocking a teammate: the blocker leaves (or, if owner, removes the blocked person).
- Closed teams deleted 90 days after closing. In-app notifications only, no email.
- **Feature switch `teams` is OFF by default**; the owner turns it on in admin Settings.

### Safety and moderation ([moderation.md](moderation.md))
- **Block** from chat, connection card or intro: two-way, ends the connection for good,
  withdraws intros, removes from matches. Unblock in Settings → Blocked people. 20/day.
- **Report** a message, intro, profile, team, team message, goal or progress note, with six
  plain reasons; a frozen copy is kept (message + 10 before it); 5/day; resolved reports
  deleted after 180 days. Reported person isn't told.
- **Content rules** flag saved requests, bios, intro notes and listed-team text for review
  (never blocks the save); **appeals** for suspensions and bans.
- Moderator alert email at most once an hour, counts only.
- Older `/moderation` page (accounts in `MODERATOR_EMAILS`) still exists beside the admin
  portal's Reports page.

### Admin portal ([ADR 0015](adr/0015-admin-portal.md), [admin-portal.md](admin-portal.md))
- `/admin`, roles `owner` (only from `ADMIN_OWNER_EMAILS`), `admin`, `moderator`,
  `readonly`; permission-checked; TOTP two-step (pyotp) with recovery codes; separate admin
  session (30 min idle, 12 h max).
- Pages: Overview, Users (suspend 7 days, ban, clear bio, notes, sign out, schedule
  deletion), Signup and access, Reports and safety, Content moderation, Matching and AI
  (probe providers, switch providers, re-run matching), Communication (banners, email log,
  template tests), Settings (feature switches and limits), Team and audit, Data and
  compliance (deletions, exports, CSV).
- Every change needs a reason (≥ 10 chars) and is written to `admin_audit_log` in the same
  transaction; a trigger forbids UPDATE/DELETE; kept forever.
- Admin code never reads chat text, except messages attached to a report.
- **Feature switches:** `intro_requests`, `chats`, `ai_matching`, `email_notifications`
  (on by default), `teams` (off). **Adjustable limits:** match requests/day, intros/day,
  max pending intros, message max length.

### Web pages
- Public: `/` (static landing, `public/landing/index.html`), `/team` (static team page),
  `/login`, `/privacy`, `/terms`, `/appeal`.
- Signed in (app shell, `app/(app)/`): `/home` (composer, requests, inline intro
  responses, summary cards with hover tilt), `/messages`, `/messages/[id]`,
  `/notifications`, `/onboarding`, `/profile`, `/you`, `/you/download`, `/saved`,
  `/settings`, `/settings/account`, `/settings/blocked`, `/teams`, `/teams/[id]`,
  `/teams/browse`, `/teams/join/[code]`, `/spaces` (redirect), `/moderation/*`.
- Nav: Home, Spaces (→ `/teams`), You, Team (→ static `/team`).
- Admin: `/admin/*` and `/admin/two-step`. Style guide `/design` (dev and previews only).

---

## 6. Data model (41 tables, migrations 0001–0034)

| Area | Tables |
| --- | --- |
| Identity and auth | `users`, `auth_identities`, `otp_codes`, `sessions`, `auth_events`, `oauth_states` |
| Profile and AI | `profiles`, `profile_embeddings` (vector(384), HNSW), `ai_calls`, `content_flags` |
| Matching | `match_requests` (nullable `team_id`), `matches` |
| Social | `intros`, `connections` (`ended_at`), `notifications`, `messages` |
| Teams / pair spaces | `teams`, `team_members`, `team_invites`, `team_messages`, `space_goals`, `space_skills`, `progress_logs` |
| Safety | `blocks`, `reports`, `moderation_actions`, `appeals` |
| Admin | `admin_accounts`, `admin_recovery_codes`, `admin_sessions`, `admin_audit_log`, `admin_notes`, `admin_exports` |
| Signup and comms | `app_settings`, `signup_domains`, `signup_applications`, `invite_codes`, `banners`, `email_sends`, `email_log` |
| Infrastructure | `jobs`, `rate_limit_counters`, `data_exports` |

Conventions: UUID keys, `timestamptz`, `CHECK` constraints instead of enums, naming
convention for constraint names, `ON DELETE CASCADE` from users. Not built yet: `events`
(behavioural log, monthly partitions), `feedback`, `skills`/`interests` vocabulary tables.

### Scheduled jobs (`app/jobs/schedule.py`)
Daily: `hard_delete_accounts`, `purge_auth_data`, `match_housekeeping`, `purge_messages`,
`purge_reports`, `purge_moderation_log`, `purge_spaces`, `purge_data_exports`.
Hourly: `purge_job_tables`, `report_alerts`.
On demand: `send_login_code`, `parse_profile`, `parse_pending_profiles`, `embed_profile`,
`reembed_profiles`, `match_request`, `send_notification_email`, `send_safety_notice`,
`send_invite`, `send_test_email`, `ai_probe`, `build_data_export`, `build_admin_export`,
`ping`. All idempotent.

### Main retention rules
OTP codes and sessions: on expiry · `auth_events` 90 d · jobs: succeeded 7 d, dead 30 d ·
email log 30 d · messages and team messages 90 d · progress notes 90 d · closed team 90 d
after closing · match requests 90 d · notifications 90 d · resolved reports 180 d after
resolving · moderation log 365 d · admin audit log forever · data-export file 72 h, row
90 d · deleted accounts hard-deleted after 30 d grace.

---

## 7. API (145 operations, `docs/api/openapi.json`, title "Cynergi API")

| Group | Paths |
| --- | --- |
| Health | `/ping`, `/health`, `/health/ready` |
| Auth | `/auth/otp/request`, `/auth/otp/verify`, `/auth/google/start`, `/auth/google/callback`, `/auth/me`, `/auth/methods`, `/auth/sessions`, `/auth/logout(-all/-others)`, `/auth/applications` |
| Me | `/me` (DELETE), `/me/pause`, `/me/resume`, `/me/profile` (GET/PUT/PATCH), `/me/profile/understanding`, `/me/data-exports` |
| Matching | `/requests`, `/requests/{id}`, `/requests/{id}/matches`, `/requests/{id}/close`, `/matches/{id}/intro`, `/skills/suggest` |
| Social | `/intros`, `/intros/{id}/respond`, `/connections`, `/connections/{id}/messages`, `/connections/{id}/read`, `/messages/updates`, `/notifications` |
| Teams | `/teams`, `/teams/{id}`, members, invites, invite-link, `join/{code}`, `listed`, requests, messages, read, `space` (goals, skills, logs) |
| Safety | `/blocks`, `/appeals`, reports on messages, intros, people, teams, team messages, space goals, progress logs |
| App | `/features`, `/banner` |
| Moderation | `/moderation/reports`, `/moderation/accounts/*`, `/moderation/ai` |
| Admin | `/admin/*` (overview, users, access, safety, content, ai, comms, settings, data, team, audit, two-step, storage, health, `jobs/tick`) |

Errors: `{"error": {"code": ..., ...}}` with stable codes (e.g. `rate_limited`,
`csrf_failed`, `consent_required`, `email_not_allowed`, `feature_off`,
`email_quota_exhausted`, `photo_unavailable`, `admin_two_step_required`).

---

## 8. Tech stack and repository

| Layer | Choice |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, psycopg 3, uv, Ruff, mypy --strict, pytest |
| AI | fastembed (ONNX) bge-small-en-v1.5; httpx to Groq and Cloudflare; prompts as versioned `.md` files in `app/ai/prompts/` |
| Other libs | pyjwt[crypto] (Google ID tokens, Fernet), pyotp (admin TOTP) |
| Frontend | Next.js 16 (App Router), React 19, TypeScript strict, Tailwind v4, zod 4, Vitest, Playwright + axe |
| Design | Design system Cynergi ([ADR 0014](adr/0014-design-system-cynergi.md), [design-spec.md](design/design-spec.md)); **dark-only theme** ([ADR 0021](adr/0021-dark-only-theme.md)); tokens in `lib/design/tokens.ts` + `app/globals.css`; components in `components/ds` (older `components/ui` until fully migrated); fonts Inter, Inter Tight, JetBrains Mono self-hosted; motion limited to spec §5 + Home card tilt ([ADR 0019](adr/0019-home-card-tilt.md)); WCAG AA contrast enforced by tests |
| Brand | Name only from `frontend/lib/brand.ts`; backend `APP_NAME` (default "Cynergi") |

```
backend/app/   main.py, core/, db/, models/, schemas/, api/v1/ (28 routers), services/
               (auth/, matching/, admin/, email/, teams, chat, …), ai/ (gateway, stages,
               prompts, providers, budget, privacy), jobs/, data/ (skill lists)
backend/migrations/versions/   0001 … 0034
backend/evals/                 synthetic eval set
backend/tests/unit, integration, fake_oidc.py
frontend/app/                  pages (see §5), api/v1/[...path] forwarder, proxy.ts
frontend/components/, lib/, e2e/
frontend/public/landing, public/team   static pages
infra/                         production.env.example, cloudflare-tick/
docs/                          ARCHITECTURE.md, adr/, design/, api/, ops docs
.github/workflows/             ci.yml, security.yml, migrate-staging.yml,
                               staging-migrations.yml, admin-perf.yml
.devcontainer/                 Codespaces (Docker-in-Docker)
```

---

## 9. How work is done

- Short-lived branch `<type>/<desc>` → PR (template in `.github/pull_request_template.md`)
  → CI green → merge. Never push to `main`. Conventional Commits.
- **Required checks** (ruleset "Protect main"): **Backend** (Ruff, format, mypy, OpenAPI
  freshness, migrations up/down/up + `alembic check`, tests, ≥ 90% auth coverage),
  **Frontend** (ESLint, Prettier, tsc, Vitest, Worker script test, build), **Docker images**
  (compose validation, image builds, 400 MB embedding memory check), **Smoke** (full stack
  healthy, Playwright e2e + axe, screenshots), **Secret scan** (gitleaks). Plus the
  **Staging migrations** drift check.
- Local checks only: Ruff, mypy, backend unit tests, frontend lint/typecheck/format/Vitest,
  OpenAPI regeneration (`uv run python -m app.openapi_export`).
- Red CI is fixed, never bypassed. One failed fix attempt → stop and tell the owner.
- After a migration PR merges: run "Migrate staging", confirm the new head and the Staging
  migrations check, report the number. **Never** migrate production.
- **Owner review (no auto-merge)** for anything touching privacy, consent, moderation,
  reporting, legal or terms wording. Other auto-merge permissions are granted per step.
- New infrastructure or major dependency → ADR. Contradicting an ADR → new ADR.

---

## 10. Environments and deployment ([deployment-plan.md](deployment-plan.md))

| Piece | Where | Status |
| --- | --- | --- |
| Database | Neon Free `skill-buddy-staging`, Singapore, 0.25 CU cap | Live |
| API | Render Free `skillbuddy-api`, Docker | Live; kept awake by UptimeRobot on `/ping` |
| Web | Vercel Hobby (non-commercial only) | Live |
| Scheduler | Cloudflare Worker `skill-buddy-tick` | Live, logging `tick ok` |
| Email | Gmail API, one account, refresh token from 2026-10-02 | Live; first real sign-in passed |
| AI keys | Groq (ZDR on) + Cloudflare, set on Render | Done 2026-10-05 |
| Google sign-in client | — | **Pending** |
| Production | — | Not set up; needs its own ADR |

Sign-in lists are deliberately empty on staging until delivery to `@thapar.edu` is tested,
so anyone who can receive a code can sign in to staging.

---

## 11. Timeline (all PRs merged in about two weeks)

| Dates | What landed |
| --- | --- |
| 2026-10-01 | Phase 0 skeleton, working rules, zero-cost and storage docs, CI (smoke, secrets), auth backend + email jobs + frontend, eval set skeleton, ADRs 0001–0008 |
| 2026-10-02 | Postgres job queue and tick, 18+ rule, 384-dim embeddings, AI gateway, Postgres rate limits, Gmail sender, design system v1, profile screens, Google sign-in, intro screens; staging went live |
| 2026-10-03 | Chat (polling), message reports, blocking, report targets, moderation page, privacy/terms rewrite, staging drift check |
| 2026-10-04/05 | Hardening (security headers, OpenAPI export, smoke proven), safety tips, one-to-one pair spaces + reports |
| 2026-10-06 | AI status page, keep-alive ping |
| 2026-10-07/08 | Redesign to Cynergi (ADR 0014), rename, landing, restyled screens, "You" page, account controls, admin portal foundation/users/safety |
| 2026-10-09 | Admin overview, signup access, settings, moderation/AI, comms, data/compliance; matcher hybrid retrieval + quality gates + LLM judge |
| 2026-10-10/11 | Match presentation, judge context, teams T1–T8, Google photo, OWASP and privacy hardening, pair spaces become teams, new landing and Home |
| 2026-10-12 | Card tilt, sign-in restyle, dark-only theme, skill suggestions, Home perf, profile nudge, static team page and nav link (last merge, #151) |

No merges since 2026-10-12.

---

## 12. Open items and loose ends

### Blocking launch (from [pre-launch-checklist.md](pre-launch-checklist.md))
- **Legal:** lawyer review reported done; still need to merge any requested changes, move
  `TERMS_VERSION` / `legal.version` off `-draft`, remove the draft notice, and replace the
  placeholder contact `privacy-contact@example.com` (`frontend/lib/legal.ts`).
- Owner review of the intro-email wording and the final AI-consent wording in the app.
- Google Cloud OAuth app to "In production"; the day-8 login-code check (due since
  2026-10-10); delivery test to `@thapar.edu`.
- Neon: scale-to-zero check (more urgent with the keep-alive ping), weekly compute-use
  check, scheduler timing check, Render memory under 430 MB.
- Re-check every free-tier row dated 2026-10-01 or older.
- Commit the owner-reviewed eval labels (main still has all `draft`); invite plan in waves
  of ~300 students a day.
- Automated screening of profiles and first messages (moderation queue exists; screening
  of message text not built, needs a consent/privacy decision).
- Real screen-reader check (NVDA, TalkBack).
- Owner dashboard steps: Render `APP_NAME=Cynergi` and `TERMS_VERSION=2026-10-08-draft`,
  `ADMIN_OWNER_EMAILS`, Google consent-screen name/logo, Gmail sender name, UptimeRobot label.

### Not blocking
Groq "consumer use" question · Vercel non-commercial confirmation · LGPL notices · Neon
0.5 vs 1 GB · eval precision@5 run · Codespace exercise · ruleset "up to date before merge" ·
business model · domain · measured per-user storage · `events`/feedback loop and learned
ranker · pair-space reminders, conversation starters, templates · normalised skill ids.

### Things to know (inconsistencies found while writing this)
- Fixed on 2026-11-10: the phase is restated in README, CLAUDE.md and ARCHITECTURE.md §11;
  the dark-only ADR is renumbered 0021 (0017 is the Google profile photo); ADR 0011 is
  Accepted; ADR 0016 notes that ADR 0018 replaced its "Pair spaces" nav item; the backend
  `TERMS_VERSION` default is `2026-10-08-draft`, matching the pages.
- The `teams` switch is off by default, so **pair spaces are invisible until turned on**
  in admin Settings, even though T8 (reports) has merged.
- **Unmerged remote branches:** `feat/allow-minors` (would remove the 18+ rule; contradicts
  ADR 0009, so it needs a new ADR if wanted), `feat/home-inline-respond` (one extra commit
  after #138), `fix/e2e-discover-opened-item`, `fix/photo-migration-number` (looks
  superseded by #128), and four Dependabot branches.
- `TERMS_VERSION` on Render is what counts on staging; the code default only matters
  where it is unset. Check that Render says `2026-10-08-draft`.

---

## 13. Where to look

| Question | File |
| --- | --- |
| Product scope, data model, roadmap | [ARCHITECTURE.md](ARCHITECTURE.md), [roadmap.md](roadmap.md) |
| Why something is the way it is | [adr/](adr/) (0001–0021) |
| Working rules for Claude Code | [../CLAUDE.md](../CLAUDE.md), [../CONTRIBUTING.md](../CONTRIBUTING.md) |
| Staging setup, step by step | [deployment-plan.md](deployment-plan.md), [../infra/README.md](../infra/README.md) |
| Launch blockers | [pre-launch-checklist.md](pre-launch-checklist.md) |
| Storage and free limits | [storage-budget.md](storage-budget.md), [free-tier-limits.md](free-tier-limits.md) |
| Moderation and admin how-to | [moderation.md](moderation.md), [admin-portal.md](admin-portal.md) |
| Manual staging tests | [staging-tests.md](staging-tests.md) |
| Design | [design/design-spec.md](design/design-spec.md), reference HTML pages in `design/` |
| API contract | [api/openapi.json](api/openapi.json) |
| Rename details | [rename.md](rename.md) |
| Morning-after notes from the redesign | [overnight-questions.md](overnight-questions.md) |
