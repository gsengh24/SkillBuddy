# Pre-launch checklist

Every open item from the ADRs, the [Phase 0 exit report](phase-0-exit-report.md) and
[ARCHITECTURE.md](ARCHITECTURE.md) that must be settled before Skill Buddy opens to the
campus. Collected on **2026-10-02**.

**Owners:**
- **Project owner:** needs a human, an account login, a legal contact or a decision.
- **Claude Code:** code, tests and docs, delivered as pull requests with green CI.

**Blocks launch:** "Yes" means sign-ups must not open to the campus until the item is done.

Tick an item in the PR that closes it, with the date and the evidence (PR, CI run, or a
short note).

## Legal, terms and privacy

| # | Item | Done when | Owner | Blocks launch | Source |
| --- | --- | --- | --- | --- | --- |
| 1 | [ ] **Legal review of the privacy policy and terms**: the DPDP Act; the 18+ rule as a self-declaration tick box ([ADR 0009](adr/0009-adults-only-self-declaration.md)), which is not verified (some students may be 17); the AI-processing wording; and data sent to Groq and Cloudflare | A lawyer has reviewed both pages; required changes are merged; `TERMS_VERSION` is bumped from `2026-10-01-draft` | Project owner | Yes | ADR 0009; ADR 0007 §5; ARCHITECTURE.md §12 |
| 2 | [ ] **Groq support question (optional)**: does "not for consumer use" allow a campus app used by students? | A written answer is saved, if asked. If Groq ever says no or withdraws the free plan, switch to `AI_LLM_PROVIDERS=cloudflare` (Cloudflare-only fallback, about 100–200 daily active users), or template-only | Project owner | No: the Cloudflare and template fallbacks cover a withdrawal | ADR 0007 §3a |
| 3 | [ ] **Onboarding consent line and final privacy wording on AI processing** shipped in the app | The text from ADR 0007 §5 is live (adjusted after item 1) | Claude Code | Yes | ADR 0007 §5 and build step 9 |
| 4 | [ ] **Vercel Hobby is for non-commercial use only**: confirm the launch is non-commercial | Owner confirms; otherwise a new hosting ADR | Project owner | No | ADR 0003 |
| 5 | [ ] **Third-party notices** for LGPL components (psycopg, sharp-libvips) | A notices file exists, if images are ever distributed | Claude Code | No | Exit report, issue 15 |

## Email (Gmail API)

| # | Item | Done when | Owner | Blocks launch | Source |
| --- | --- | --- | --- | --- | --- |
| 6 | [ ] **Google Cloud OAuth app set to "In production"**, not "Testing" (Testing-mode refresh tokens for `gmail.send` expire after 7 days) | Screenshot or note of Google Auth Platform → Audience → Publishing status; the refresh token was created *after* the switch | Project owner | Yes | ADR 0008, "Pre-launch checks" |
| 7 | [ ] **Day-8 login-code check**: a real login code still arrives 8 or more days after the refresh token was issued, with no `invalid_grant` in the email job's log | The date of the passing check is recorded here | Project owner (Claude Code reads the logs) | Yes | ADR 0008, "Pre-launch checks" |
| 8 | [ ] **Delivery to `@thapar.edu`**: <ul><li>look up the MX host;</li><li>send codes to 3–5 volunteer student addresses, with their consent;</li><li>record inbox, junk or quarantine for each;</li><li>check the headers show `spf=pass`, `dkim=pass`, `dmarc=pass`;</li><li>ask college IT to allow-list the sender if mail lands in quarantine.</li></ul> | Every volunteer address receives the code in the inbox | Project owner (Claude Code writes the steps) | Yes | ADR 0008, "Testing deliverability" |
| 9 | [ ] **Email cap and reserve built**: `EMAIL_DAILY_CAP=450`, a reserve for login codes, and `503 email_quota_exhausted` | ADR 0008 step 5 merged | Claude Code | Yes | ADR 0008 |

## Hosting, database and scheduling

| # | Item | Done when | Owner | Blocks launch | Source |
| --- | --- | --- | --- | --- | --- |
| 10 | [ ] **ADR 0008 build steps 3–6** (step 1 tables and step 2 job runner are done: #18, #20; still to do: ported jobs and tick endpoint, Postgres rate limiter with Arq and Valkey removed, Gmail sender, docs) | All merged with green CI | Claude Code | Yes | ADR 0008 |
| 11 | [ ] **Staging prerequisites**: API listens on `$PORT`, `postgresql://` URLs accepted, "Migrate staging" workflow | Merged; a manual migration run against Neon succeeds | Claude Code | Yes | deployment-plan.md; exit report, issue 6 |
| 12 | [ ] **Render Free accepts our service** (Docker runtime, or the native Python fallback) | The API is deployed and `/api/v1/health` answers | Project owner (Claude Code gives the click-by-click steps) | Yes | deployment-plan.md; exit report, risk 4 |
| 13 | [ ] **Neon storage: 1 GB or 0.5 GB?** The pricing page now says 1 GB per project, but the storage budget assumes 0.5 GB | The limit is re-checked in the Neon console. If it is 1 GB, `DATABASE_SIZE_LIMIT_MB` and storage-budget.md are updated; if not, nothing changes | Claude Code (owner confirms in the console) | No: the 0.5 GB budget is the safe side | ADR 0008, "Not verified" |
| 14 | [ ] **Neon autoscaling capped at 0.25 CU** | Set in the Neon console | Project owner | Yes | ADR 0008, decision 6 |
| 15 | [ ] **Neon scale-to-zero with an idle connection pool**: does an awake API with idle pooled connections keep Neon from suspending? | Measured on staging. If idle connections block suspend, the pool closes idle connections or uses `NullPool` | Claude Code (owner reads the Neon graph) | Yes | ADR 0008, "Not verified" |
| 16 | [ ] **Neon compute-use monitoring** | An admin endpoint shows CU-hours used, or a weekly manual check is agreed; 70% before day 21 triggers action | Claude Code / project owner | Yes | ADR 0008, decision 6 |
| 17 | [ ] **Scheduler timing check**: the Cloudflare Worker cron fires hourly from 02:30 to 17:30 UTC (08:00–23:00 IST) and at 00:30 UTC, each tick reaches the API, and the scheduled jobs run once per day | Tick times over 2 days are recorded from the API logs; housekeeping and retention jobs show one run per day; the extra Neon CU from ticks is noted | Project owner sets up the Worker; Claude Code verifies the logs | Yes | ADR 0008, decision 2 |
| 18 | [ ] **Memory on the 512 MB host**: CI records peak RSS with the embedding model below 400 MB; Render stays below 430 MB in use | The CI step is green and the Render metrics are checked after launch-week load | Claude Code | Yes | ADR 0007 §1; ADR 0008, decision 4 |
| 19 | [ ] **Free-tier limits re-checked**: every row in free-tier-limits.md that is dated 2026-10-01 or older | Rows re-dated within a week of launch | Claude Code | Yes | ADR 0004; free-tier-limits.md |

## AI providers and matching quality

| # | Item | Done when | Owner | Blocks launch | Source |
| --- | --- | --- | --- | --- | --- |
| 20 | [ ] **Cloudflare `@cf/openai/gpt-oss-20b` on the Workers Free plan**: is it available? | Checked in the Cloudflare dashboard. If it is not available, set the Cloudflare model to `llama-3.1-8b-instruct-fp8-fast` | Project owner | No (there is a fallback model) | ADR 0007 §3a, "Not verified" |
| 21 | [ ] **Groq and Cloudflare accounts** created without a card; Groq Zero Data Retention on; keys only in the hosting dashboard | Owner confirms each point | Project owner | Yes | ADR 0007, build step 11 |
| 22 | [ ] **ADR 0007 AI build steps 2–9** (384-dimension migration 0004, embedder, gateway, providers, stages 1–4, onboarding text) | All merged with green CI | Claude Code | Yes | ADR 0007 |
| 23 | [ ] **Review the 100 draft evaluation labels** and mark them `reviewed` | `review_status` is `reviewed` for every pair; `explore` rebalanced | Project owner | Yes | Exit report, blocker 2 |
| 24 | [ ] **Eval run**: precision@5 for the LLM path and the fallback path | Numbers recorded in the evals README | Claude Code | No | ADR 0007, build step 10 |
| 25 | [ ] **Invite plan**: waves of about 300 students per day, matched to LLM and email capacity | Owner agrees the wave sizes and dates | Project owner | Yes | ADR 0007 §4; ADR 0008 |

## Safety, security and accessibility

| # | Item | Done when | Owner | Blocks launch | Source |
| --- | --- | --- | --- | --- | --- |
| 26 | [ ] **Block, report and rate limits on intros** built before sign-ups open to the campus | Merged with tests: blocks are a hard filter in retrieval, and intros per day are limited | Claude Code | Yes | ARCHITECTURE.md §8 ("part of the launch scope") |
| 27 | [ ] **Screening of profiles and first messages, plus a human moderation queue** | Merged with tests; the owner knows how to work the queue | Claude Code (queue is worked by the project owner) | Yes | ARCHITECTURE.md §8 |
| 28 | [ ] **Safety nudges** (first-chat tips) | Shown in the first chat | Claude Code | Yes | ARCHITECTURE.md §8 |
| 29 | [ ] **Security headers on web pages** are tested, not just configured (`frontend/next.config.ts` `headers()`) | A test asserts CSP, `X-Content-Type-Options`, `Referrer-Policy`, frame protection, and HSTS when deployed, on the web pages | Claude Code | Yes | Exit report, criterion 5 ("Implemented, untested") |
| 30 | [ ] **Real screen-reader check** of sign-in, account settings, onboarding and matches, with NVDA (Windows) and TalkBack (Android) | Each flow completed by ear, problems fixed | Project owner (Claude Code fixes the findings) | Yes | Accessibility claims in `login-form.tsx` (labelled fields, `role="alert"`/`role="status"`) were tested only in component tests |
| 31 | [ ] **Smoke job proven to fail** (a throwaway PR that breaks readiness) | CI goes red on that PR, which is then closed | Claude Code | No | Exit report, issue 10 |

## Housekeeping and open decisions

| # | Item | Done when | Owner | Blocks launch | Source |
| --- | --- | --- | --- | --- | --- |
| 32 | [ ] **Exercise the Codespace** end to end once | Stack up and sign-in works in a Codespace | Project owner | No | Exit report, issue 7 |
| 33 | [ ] **Export the OpenAPI spec** to the repository | A committed spec, checked in CI | Claude Code | No | Exit report, issue 9 |
| 34 | [x] **Dependabot `uv` run** succeeds after the redis cap (moot once Redis is removed in ADR 0008 step 4) | The next weekly run is green, or the item is closed by step 4 | Claude Code | No | Exit report, issue 11 |
| 35 | [ ] **Ruleset: require branches to be up to date** before merging | Decided in the repository settings | Project owner | No | Exit report, issue 12 |
| 36 | [ ] **Remove the unused `NEXT_PUBLIC_API_URL`** from `docker-compose.yml` | Merged | Claude Code | No | Exit report, issue 13 |
| 37 | [ ] **Business model** decision | Recorded in ARCHITECTURE.md §12 | Project owner | No | ARCHITECTURE.md §12 |
| 38 | [ ] **Platform name and brand** (the email sender name, and a domain later) | Recorded; `lib/brand.ts` and the sender name updated | Project owner | No | ARCHITECTURE.md §12 |
| 39 | [ ] **Owner dashboard steps**: Gmail account and OAuth client, Cloudflare Worker and `JOBS_TICK_TOKEN`, Render environment variables | Done, following the steps Claude Code writes into deployment-plan.md (ADR 0008 step 6) | Project owner | Yes | ADR 0008, build step 7 |

Already decided (ARCHITECTURE.md §12): the launch community is one college campus; the
team is a solo build with Claude Code; hosting is the zero-cost free tiers (ADR 0003,
ADR 0004); English only at launch (ADR 0007).
