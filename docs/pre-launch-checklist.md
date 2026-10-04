# Pre-launch checklist

Every open item from the ADRs, the [Phase 0 exit report](phase-0-exit-report.md) and
[ARCHITECTURE.md](ARCHITECTURE.md) that must be settled before Skill Buddy opens to the
campus. Collected on **2026-10-02**; staging status updated on **2026-10-02** (staging is live, first sign-in passed; see [deployment-plan.md](deployment-plan.md#staging-status-2026-10-02)).

**Owners:**
- **Project owner:** needs a human, an account login, a legal contact or a decision.
- **Claude Code:** code, tests and docs, delivered as pull requests with green CI.

**Blocks launch:** "Yes" means sign-ups must not open to the campus until the item is done.

Tick an item in the PR that closes it, with the date and the evidence (PR, CI run, or a
short note).

## Legal, terms and privacy

| # | Item | Done when | Owner | Blocks launch | Source |
| --- | --- | --- | --- | --- | --- |
| 1 | [ ] **Legal review of the privacy policy and terms**: the DPDP Act; the 18+ rule as a self-declaration tick box ([ADR 0009](adr/0009-adults-only-self-declaration.md)), which is not verified (some students may be 17); the AI-processing wording; and data sent to Groq and Cloudflare | A lawyer has reviewed both pages; required changes are merged; `TERMS_VERSION` (and `version` in `frontend/lib/legal.ts`) is bumped from `2026-10-04-draft` to a non-draft version | Project owner | Yes | ADR 0009; ADR 0007 §5; ARCHITECTURE.md §12 |
| 2 | [ ] **Groq support question (optional)**: does "not for consumer use" allow a campus app used by students? | A written answer is saved, if asked. If Groq ever says no or withdraws the free plan, switch to `AI_LLM_PROVIDERS=cloudflare` (Cloudflare-only fallback, about 100–200 daily active users), or template-only | Project owner | No: the Cloudflare and template fallbacks cover a withdrawal | ADR 0007 §3a |
| 3 | [ ] **Onboarding consent line and final privacy wording on AI processing** shipped in the app (progress 2026-10-03, step 7d: the ADR 0007 §5 wording is live at `/privacy#ai`; final after item 1) | The text from ADR 0007 §5 is live (adjusted after item 1). Consent line: on the profile form (recorded with `AI_CONSENT_VERSION`), awaiting owner review. Policy wording and the `/privacy#ai` section: not yet | Claude Code | Yes | ADR 0007 §5 and build step 9 |
| 4 | [ ] **Vercel Hobby is for non-commercial use only**: confirm the launch is non-commercial | Owner confirms; otherwise a new hosting ADR | Project owner | No | ADR 0003 |
| 5 | [ ] **Third-party notices** for LGPL components (psycopg, sharp-libvips) | A notices file exists, if images are ever distributed | Claude Code | No | Exit report, issue 15 |
| 42 | [ ] (toggle built in step 7d: Account settings, Emails, "Emails about intros"; wording "We email you when someone sends you an intro or accepts yours.") **Owner review before any production migration that touches consent**: migration 0008 adds `profiles.email_notifications` with a default of **on** for every existing profile (intro emails). Before running migrations on production, stop and show the owner that default and the wording of the email toggle in settings | Owner has approved the default and the toggle wording, in writing, before the production migration runs | Project owner (Claude Code prepares the review) | Yes | Migration 0008; PR #39 |
| 43 | [ ] **Replace the placeholder contact address** (`privacy-contact@example.com`) on the privacy policy and terms. It is defined in one place: `contactEmail` in `frontend/lib/legal.ts` | A real address the owner reads is set there and shown on `/privacy` and `/terms` | Project owner (Claude Code makes the change) | Yes | Step 7d |

## Email (Gmail API)

| # | Item | Done when | Owner | Blocks launch | Source |
| --- | --- | --- | --- | --- | --- |
| 6 | [ ] **Google Cloud OAuth app set to "In production"**, not "Testing" (Testing-mode refresh tokens for `gmail.send` expire after 7 days) | Screenshot or note of Google Auth Platform → Audience → Publishing status; the refresh token was created *after* the switch | Project owner | Yes | ADR 0008, "Pre-launch checks" |
| 7 | [ ] **Day-8 login-code check, due on or after 2026-10-10** (refresh token created 2026-10-02): a real login code still arrives 8 or more days after the refresh token was issued, with no `invalid_grant` in the email job's log | The date of the passing check is recorded here | Project owner (Claude Code reads the logs) | Yes | ADR 0008, "Pre-launch checks" |
| 41 | [ ] **Day-8 check on 2026-10-10 or later**: sign in to staging with a fresh code on or after **10 October 2026** and confirm the code arrives, with no `invalid_grant` in the Render logs. If it fails, the Gmail OAuth app was still in "Testing" when the token was made: publish it "In production" and create a new refresh token (deployment-plan.md step 2) | The date of the passing check is recorded here and in item 7 | Project owner (Claude Code reads the logs) | Yes | ADR 0008, "Pre-launch checks" |
| 8 | [ ] **Delivery to `@thapar.edu`** (pending; the three sign-in lists stay empty on staging until this is done): <ul><li>look up the MX host;</li><li>send codes to 3–5 volunteer student addresses, with their consent;</li><li>record inbox, junk or quarantine for each;</li><li>check the headers show `spf=pass`, `dkim=pass`, `dmarc=pass`;</li><li>ask college IT to allow-list the sender if mail lands in quarantine.</li></ul> | Every volunteer address receives the code in the inbox | Project owner (Claude Code writes the steps) | Yes | ADR 0008, "Testing deliverability" |
| 9 | [x] **Email cap and reserve built** (Gmail API sender, ADR 0008 step 5): `EMAIL_DAILY_CAP=450`, a reserve for login codes, and `503 email_quota_exhausted` | ADR 0008 step 5 merged | Claude Code | Yes | ADR 0008 |

## Hosting, database and scheduling

| # | Item | Done when | Owner | Blocks launch | Source |
| --- | --- | --- | --- | --- | --- |
| 10 | [x] **ADR 0008 build steps 1–6** (job tables, runner, ported jobs and tick endpoint, PostgreSQL rate limits with Arq and Valkey removed, Gmail sender, docs: #18, #20, #23, #28, #30 and the staging-setup PR) | All merged with green CI | Claude Code | Yes | ADR 0008 |
| 11 | [x] **Staging prerequisites**: API listens on `$PORT`, `postgresql://` URLs accepted, "Migrate staging" workflow | Merged; a manual migration run against Neon succeeds (done 2026-10-02, after #35: migration 0006 applied) | Claude Code | Yes | deployment-plan.md; exit report, issue 6 |
| 12 | [x] **Render Free accepts our service** (Docker runtime, or the native Python fallback) | The API is deployed and `/api/v1/health` answers. Done 2026-10-02: Docker runtime, Free, Singapore; health check passes | Project owner (Claude Code gives the click-by-click steps) | Yes | deployment-plan.md; exit report, risk 4 |
| 13 | [ ] **Neon storage: 1 GB or 0.5 GB?** The pricing page now says 1 GB per project, but the storage budget assumes 0.5 GB | The limit is re-checked in the Neon console. If it is 1 GB, `DATABASE_SIZE_LIMIT_MB` and storage-budget.md are updated; if not, nothing changes | Claude Code (owner confirms in the console) | No: the 0.5 GB budget is the safe side | ADR 0008, "Not verified" |
| 14 | [x] **Neon autoscaling capped at 0.25 CU** | Set in the Neon console. Done 2026-10-02 (PostgreSQL 16, Singapore) | Project owner | Yes | ADR 0008, decision 6 |
| 15 | [ ] **Neon scale-to-zero with an idle connection pool**: does an awake API with idle pooled connections keep Neon from suspending? | Measured on staging. If idle connections block suspend, the pool closes idle connections or uses `NullPool` | Claude Code (owner reads the Neon graph) | Yes | ADR 0008, "Not verified" |
| 16 | [ ] **Neon compute-use monitoring: a weekly manual check** (owner decision 2026-10-04: no Neon API key). Every week: Neon console → your project → **Monitoring** (or **Billing → Usage**) → note the compute hours used this month against 100 CU-hours. If more than 70% is used before day 21 of the month, tell Claude Code (fewer scheduler ticks, shorter polling, or a pause) | The weekly check is happening and its last date is written here | Project owner | Yes | ADR 0008, decision 6 |
| 17 | [ ] **Scheduler timing check** (Worker `skill-buddy-tick` deployed 2026-10-02 and logging `tick ok`; the 2-day check is still open): the Cloudflare Worker cron fires hourly from 02:30 to 17:30 UTC (08:00–23:00 IST) and at 00:30 UTC, each tick reaches the API, and the scheduled jobs run once per day | Tick times over 2 days are recorded from the API logs; housekeeping and retention jobs show one run per day; the extra Neon CU from ticks is noted | Project owner sets up the Worker; Claude Code verifies the logs | Yes | ADR 0008, decision 2 |
| 18 | [ ] **Memory on the 512 MB host**: CI records peak RSS with the embedding model below 400 MB; Render stays below 430 MB in use | The CI step is green and the Render metrics are checked after launch-week load | Claude Code | Yes | ADR 0007 §1; ADR 0008, decision 4 |
| 19 | [ ] **Free-tier limits re-checked**: every row in free-tier-limits.md that is dated 2026-10-01 or older | Rows re-dated within a week of launch | Claude Code | Yes | ADR 0004; free-tier-limits.md |

## AI providers and matching quality

| # | Item | Done when | Owner | Blocks launch | Source |
| --- | --- | --- | --- | --- | --- |
| 20 | [ ] **Cloudflare `@cf/openai/gpt-oss-20b` on the Workers Free plan**: is it available? | Checked in the Cloudflare dashboard. If it is not available, set the Cloudflare model to `llama-3.1-8b-instruct-fp8-fast` | Project owner | No (there is a fallback model) | ADR 0007 §3a, "Not verified" |
| 21 | [ ] **Groq and Cloudflare accounts** (pending: no AI keys on staging yet) created without a card; Groq Zero Data Retention on; keys only in the hosting dashboard | Owner confirms each point | Project owner | Yes | ADR 0007, build step 11 |
| 22 | [ ] **ADR 0007 AI build steps 2–9** (384-dimension migration 0004, embedder, gateway, providers, stages 1–4, onboarding text) | All merged with green CI | Claude Code | Yes | ADR 0007 |
| 23 | [ ] **Review the 100 draft evaluation labels** and mark them `reviewed` | `review_status` is `reviewed` for every pair; `explore` rebalanced | Project owner | Yes | Exit report, blocker 2 |
| 24 | [ ] **Eval run**: precision@5 for the LLM path and the fallback path | Numbers recorded in the evals README. Template-path baseline recorded 2 Oct 2026 (`evals/quality.py`); LLM path waits on item 23 and a provider key | Claude Code | No | ADR 0007, build step 10 |
| 25 | [ ] **Invite plan**: waves of about 300 students per day, matched to LLM and email capacity | Owner agrees the wave sizes and dates | Project owner | Yes | ADR 0007 §4; ADR 0008 |

## Safety, security and accessibility

| # | Item | Done when | Owner | Blocks launch | Source |
| --- | --- | --- | --- | --- | --- |
| 26 | [x] **Block, report and rate limits on intros** built before sign-ups open to the campus (done 2026-10-03: blocking in step 7a, #49; reporting messages, intros and profiles in step 7b; intro limits since #39) | Merged with tests: blocks are a hard filter in retrieval, and intros per day are limited | Claude Code | Yes | ARCHITECTURE.md §8 ("part of the launch scope") |
| 27 | [ ] **Screening of profiles and first messages, plus a human moderation queue** (progress 2026-10-03: the moderation queue is built in step 7c, with suspend and an audit log; automated screening is not built and still needs a decision) | Merged with tests; the owner knows how to work the queue | Claude Code (queue is worked by the project owner) | Yes | ARCHITECTURE.md §8 |
| 28 | [ ] **Safety nudges** (first-chat tips) | Shown in the first chat | Claude Code | Yes | ARCHITECTURE.md §8 |
| 29 | [x] **Security headers on web pages** are tested, not just configured (`frontend/next.config.ts` `headers()`; done in step 8c, 2026-10-04: CSP and HSTS added in `frontend/lib/security-headers.ts`, unit-tested for production and development, and checked on real pages with no CSP violations by the Smoke job; production headers on Vercel to be glanced at once after deploy) | A test asserts CSP, `X-Content-Type-Options`, `Referrer-Policy`, frame protection, and HSTS when deployed, on the web pages | Claude Code | Yes | Exit report, criterion 5 ("Implemented, untested") |
| 30 | [ ] **Real screen-reader check** of sign-in, account settings, onboarding and matches, with NVDA (Windows) and TalkBack (Android) | Each flow completed by ear, problems fixed | Project owner (Claude Code fixes the findings) | Yes | Accessibility claims in `login-form.tsx` (labelled fields, `role="alert"`/`role="status"`) were tested only in component tests |
| 40 | [ ] **Google sign-in tested early with a real `@thapar.edu` account** (pending: the OAuth client in step 6b is not set up yet) (ADR 0011): <ul><li>OAuth client created and the consent screen published "In production" (deployment-plan.md step 6b);</li><li>a volunteer student signs in with Google on staging and lands signed in;</li><li>if Google shows "Access blocked" (Thapar's Workspace restricts third-party apps), college IT is asked to allow the client ID;</li><li>a non-thapar Google account is refused with `email_not_allowed`.</li></ul> | A real thapar.edu account signs in with Google, or the block is known and email codes are confirmed as the way in | Project owner (Claude Code reads the logs) | No: email codes still work | ADR 0011 |
| 31 | [x] **Smoke job proven to fail** (a throwaway PR that breaks readiness; done 2026-10-04 in step 8e: throwaway PR #57 made readiness return 503 in the Docker stack only; Backend passed and Smoke failed with "container matchmaking-api-1 is unhealthy" (CI run 37148781784); #57 was closed unmerged) | CI goes red on that PR, which is then closed | Claude Code | No | Exit report, issue 10 |

## Housekeeping and open decisions

| # | Item | Done when | Owner | Blocks launch | Source |
| --- | --- | --- | --- | --- | --- |
| 32 | [ ] **Exercise the Codespace** end to end once | Stack up and sign-in works in a Codespace | Project owner | No | Exit report, issue 7 |
| 33 | [x] **Export the OpenAPI spec** to the repository (done in step 8d, 2026-10-04: `docs/api/openapi.json`, checked by the Backend CI job; regenerate with `uv run python -m app.openapi_export`) | A committed spec, checked in CI | Claude Code | No | Exit report, issue 9 |
| 34 | [x] **Dependabot `uv` run** succeeds after the redis cap (moot once Redis is removed in ADR 0008 step 4) | The next weekly run is green, or the item is closed by step 4 | Claude Code | No | Exit report, issue 11 |
| 35 | [ ] **Ruleset: require branches to be up to date** before merging | Decided in the repository settings | Project owner | No | Exit report, issue 12 |
| 36 | [x] **Remove the unused `NEXT_PUBLIC_API_URL`** from `docker-compose.yml` (done in step 8b, 2026-10-04) | Merged | Claude Code | No | Exit report, issue 13 |
| 37 | [ ] **Business model** decision | Recorded in ARCHITECTURE.md §12 | Project owner | No | ARCHITECTURE.md §12 |
| 38 | [ ] **Platform name and brand** (the email sender name, and a domain later) | Recorded; `lib/brand.ts` and the sender name updated | Project owner | No | ARCHITECTURE.md §12 |
| 39 | [ ] **Owner dashboard steps** (click-by-click in [deployment-plan.md](deployment-plan.md), steps 1–9): Gmail account and OAuth client, Cloudflare Worker and `JOBS_TICK_TOKEN`, Render environment variables | Done, following the steps Claude Code writes into deployment-plan.md (ADR 0008 step 6). 2026-10-02: steps 1, 2, 4, 5, 6 and 7 done (first sign-in passed); step 3 (AI keys) and 6b (Google client) pending; steps 8 and 9 open | Project owner | Yes | ADR 0008, build step 7 |

Already decided (ARCHITECTURE.md §12): the launch community is one college campus; the
team is a solo build with Claude Code; hosting is the zero-cost free tiers (ADR 0003,
ADR 0004); English only at launch (ADR 0007).
