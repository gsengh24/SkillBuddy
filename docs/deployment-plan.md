# Zero-cost staging: plan and click-by-click setup

**Status:** staging is live (2026-10-02); see the status table below. Decisions: [ADR 0003](adr/0003-hosting.md)
(hosting), [ADR 0007](adr/0007-ai-gateway.md) (AI), [ADR 0008](adr/0008-free-runtime-jobs-and-email.md)
(jobs, scheduler, email). Free-tier limits were checked on **2026-10-01**; re-check each
pricing page before you rely on it ([free-tier-limits.md](free-tier-limits.md)).

Total cost: **$0/month**. No step asks for a card; if a page does, stop and do not add one.
**Nothing secret goes in the repository.** Every secret is pasted into a provider dashboard
or a GitHub repository secret, and never into chat, email or a committed file.

## Staging status (2026-10-02)

| Step | What | Status |
| --- | --- | --- |
| 1 | Neon: PostgreSQL 16, Singapore, autoscaling capped at 0.25 CU | Done |
| 1 | "Migrate staging" workflow run after #35 (head is migration 0006) | Done |
| 2 | Gmail sending account and OAuth client; refresh token created 2026-10-02 | Done; day-8 check due on or after **2026-10-10** (step 9) |
| 3 | Groq and Cloudflare Workers AI keys | **Pending**: matching uses the template fallback until then |
| 4 | API on Render Free (Docker, Singapore); `/api/v1/health` passes | Done |
| 5 | Cloudflare cron Worker `skill-buddy-tick` deployed; its log shows `tick ok` | Done; the 2-day timing check is still open (checklist item 17) |
| 6 | Web app on Vercel Hobby, using `API_INTERNAL_URL` | Done |
| 6b | Google sign-in OAuth client | **Pending** |
| 7 | First sign-in: a real code sent by the Gmail API sender and accepted (2026-10-02) | **Passed** |
| 8 | Delivery to `@thapar.edu` | **Pending** |
| 9 | Day-8 check | **Due on or after 2026-10-10** |

`ALLOWED_EMAIL_DOMAINS`, `ALLOWED_EMAILS` and `BLOCKED_EMAILS` are **intentionally empty**
on staging until the `@thapar.edu` delivery test (step 8) is finished. Until then anyone
who can receive a code can sign in to staging.

## The setup at a glance

```
Browser ──► Vercel (Next.js web app, free)
               │  server-side calls over HTTPS (same-origin /api/v1 forwarder)
               ▼
            Render Free (FastAPI API, sleeps after 15 min idle)
               │  runs every background job in-process (JOBS_RUN_IN_API=true)
               ├──► Neon Free (PostgreSQL 16 + pgvector): data, job queue, rate limits, AI caps
               ├──► Gmail API (sign-in emails, 450/day cap)
               ├──► Google sign-in (OpenID Connect, optional; @thapar.edu only)
               └──► Groq, then Cloudflare Workers AI (LLM; optional, templates without them)

Cloudflare Worker (cron, 17x a day) ──► POST /api/v1/admin/jobs/tick on the API
GitHub Actions "Migrate staging" (by hand) ──► alembic upgrade head on Neon
```

Regions: Singapore for Render and Neon (AWS `ap-southeast-1`), close to India.

## Before you start

- **Time:** about 1.5 hours in one sitting, plus a check on day 8 (step 9).
- **Accounts:** GitHub (you have it), plus new free accounts at Neon, Render, Vercel,
  Cloudflare, Google (a new Gmail address just for sending), and optionally Groq.
- **A place to keep secrets while you work:** a password manager. You will copy about 10 values.
- **Two random secrets.** On your laptop, in a terminal, run this twice:
  ```
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
  Save the first output as **JOBS_TICK_TOKEN** and the second as **SECRET_KEY** in your
  password manager.

Do the steps in order: later ones need values from earlier ones.

## Step 1. Neon (database)

1. Go to **https://neon.com**, click **Sign up**, choose **Continue with GitHub**.
2. Create a project: name `skill-buddy-staging`, Postgres version **16**, region
   **AWS Asia Pacific 1 (Singapore)**. Click **Create project**.
3. **Cap the compute at 0.25 CU** (ADR 0008: keeps you inside 100 CU-hours a month):
   left menu **Branches** → click **main** → in the **Computes** section click **Edit** (the
   pencil next to the primary compute) → drag both ends of the **autoscaling** range to
   **0.25 CU** → **Save**. (Scale to zero after 5 minutes is fixed on Free; leave it.)
4. Get the connection string: top of the project dashboard → **Connect** → Branch `main`,
   Database `neondb`, Role `neondb_owner` → turn **Connection pooling off** → click the
   **copy** icon. It starts with `postgresql://` and ends with `?sslmode=require`; the app
   accepts it as is. Save it as **DATABASE_URL**.
5. In GitHub: open **https://github.com/gsengh24/SkillBuddy** → **Settings** → **Secrets and
   variables** → **Actions** → **New repository secret** → Name `STAGING_DATABASE_URL`,
   Secret = the DATABASE_URL → **Add secret**.
6. Create the tables: **Actions** tab → left list **Migrate staging** → **Run workflow** →
   branch `main` → **Run workflow**. Wait for the green tick (about 1 minute). The last step
   prints the current revision (the newest file in `backend/migrations/versions/`).

## Step 2. Gmail account and OAuth app (sign-in emails)

Render Free blocks SMTP, so the API sends through the Gmail API (ADR 0008). You create a
Gmail address only for sending, a Google Cloud project with an OAuth app, and a refresh
token. **The OAuth app must be "In production", not "Testing", before you create the
refresh token:** tokens from a Testing app stop working after 7 days.

**2a. A Gmail address for sending**

1. In a private browser window go to **https://accounts.google.com/signup** and create an
   account with any free name (for example `<project-name>.mail@gmail.com`). Save the address as **GMAIL_SENDER**.
2. Stay signed in to this account for the rest of step 2.

**2b. Google Cloud project and Gmail API (no billing)**

1. Go to **https://console.cloud.google.com** and accept the terms. If asked to start a
   free trial or add billing, **close it**: nothing here needs billing.
2. Top bar project picker → **New project** → name `skill-buddy-mail` → **Create** → select it.
3. Top search bar: type **Gmail API** → open it → **Enable**.

**2c. OAuth app (consent screen), then publish it**

1. Left menu (≡) → **APIs & Services** → **OAuth consent screen** (also shown as **Google
   Auth Platform**) → **Get started**.
2. App name `Skill Buddy mail`, User support email = your GMAIL_SENDER → **Next** →
   Audience **External** → **Next** → Contact email = your GMAIL_SENDER → **Next** → tick
   the agreement → **Continue** → **Create**.
3. Left: **Data Access** → **Add or remove scopes** → in the filter type `gmail.send` →
   tick **`.../auth/gmail.send`** → **Update** → **Save**.
4. Left: **Audience** → under Publishing status click **Publish app** → **Confirm**. The
   status must now read **In production**. (Google may mention verification; you do not
   need it, because only you will authorise this app.)

**2d. OAuth client**

1. Left: **Clients** → **Create client** → Application type **Web application** → Name
   `oauth-playground`.
2. Under **Authorized redirect URIs** click **Add URI** and paste exactly:
   `https://developers.google.com/oauthplayground`
3. **Create**. Copy the **Client ID** (save as **GMAIL_CLIENT_ID**) and the **Client secret**
   (save as **GMAIL_CLIENT_SECRET**).

**2e. Refresh token (OAuth Playground)**

1. Open **https://developers.google.com/oauthplayground**.
2. Click the **gear icon** (top right) → tick **Use your own OAuth credentials** → paste
   GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET → close the panel.
3. Left side, in **Input your own scopes**, paste `https://www.googleapis.com/auth/gmail.send`
   → **Authorize APIs**.
4. Choose your GMAIL_SENDER account. On "Google hasn't verified this app": **Advanced** →
   **Go to Skill Buddy mail (unsafe)** → **Continue** / **Allow**.
5. Back in the Playground: **Exchange authorization code for tokens**. Copy the
   **Refresh token** (starts with `1//`) and save it as **GMAIL_REFRESH_TOKEN**.
6. Write down today's date next to it: the **day-8 check** (step 9) counts from here.

## Step 3. Groq and Cloudflare AI keys (optional; matching works without them)

Without these the gateway uses template explanations. You can add them later.

1. **Groq:** **https://console.groq.com** → sign in → **Settings → Data Controls** → turn on
   **Zero Data Retention** → left **API Keys** → **Create API Key** → name
   `skill-buddy-staging` → **Submit** → copy (starts with `gsk_`) → save as **GROQ_API_KEY**.
2. **Cloudflare account** (needed for step 5 anyway): **https://dash.cloudflare.com/sign-up**
   → free plan, no card. On the account home, copy **Account ID** (right side, 32
   characters) → save as **CLOUDFLARE_ACCOUNT_ID**.
3. **Cloudflare AI token:** profile icon (top right) → **My Profile** → **API Tokens** →
   **Create Token** → template **Workers AI** → **Use template** → Account Resources:
   **Include → your account** → **Continue to summary** → **Create Token** → copy → save as
   **CLOUDFLARE_API_TOKEN**.
4. **Check the backup model is free:** left **AI → Workers AI → Models** → search
   `gpt-oss-20b`. If it is marked as needing **Workers Paid**, you will set
   `CLOUDFLARE_MODEL` to `@cf/meta/llama-3.1-8b-instruct-fp8-fast` in step 4.

## Step 4. API on Render Free

1. Go to **https://render.com** → **Get Started** → **GitHub**. Do **not** add a payment
   method.
2. **+ New** → **Web Service** → connect GitHub → pick **gsengh24/SkillBuddy**.
3. Fill in:
   - Name `skillbuddy-api`, Region **Singapore**, Branch `main`.
   - Language/Runtime **Docker**, Root Directory `backend`, Dockerfile Path
     `./Dockerfile`. (The image's last stage is the production image, with the embedding
     model built in. It listens on Render's `$PORT`.)
   - Instance type **Free**. If Free is not offered for Docker, choose runtime **Python 3**
     instead: Build Command `pip install uv && uv sync --frozen --no-dev`, Start Command
     `uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port $PORT`, and add
     the variable `EMBEDDING_CACHE_DIR` = `/opt/render/project/models` (the model then
     downloads on first use).
4. **Advanced** → **Health Check Path** `/api/v1/health` (never `/health/ready`: it would
   keep Neon awake).
5. **Environment Variables** → add each (Key = Value). Secrets are the values you saved:

   | Key | Value |
   | --- | --- |
   | `ENVIRONMENT` | `staging` |
   | `SECRET_KEY` | your SECRET_KEY |
   | `DATABASE_URL` | your DATABASE_URL |
   | `CORS_ALLOW_ORIGINS` | `https://example.invalid` for now (step 6 replaces it) |
   | `API_DOCS_ENABLED` | `true` |
   | `FORWARDED_ALLOW_IPS` | `*` (Render's proxy addresses are not fixed) |
   | `JOBS_RUN_IN_API` | `true` |
   | `JOBS_TICK_TOKEN` | your JOBS_TICK_TOKEN |
   | `EMAIL_BACKEND` | `gmail_api` |
   | `GMAIL_SENDER` | your GMAIL_SENDER |
   | `GMAIL_CLIENT_ID` | your GMAIL_CLIENT_ID |
   | `GMAIL_CLIENT_SECRET` | your GMAIL_CLIENT_SECRET |
   | `GMAIL_REFRESH_TOKEN` | your GMAIL_REFRESH_TOKEN |
   | `GROQ_API_KEY` | your GROQ_API_KEY (optional) |
   | `CLOUDFLARE_ACCOUNT_ID` | your CLOUDFLARE_ACCOUNT_ID (optional) |
   | `CLOUDFLARE_API_TOKEN` | your CLOUDFLARE_API_TOKEN (optional) |
   | `CLOUDFLARE_MODEL` | only if step 3.4 said Workers Paid: `@cf/meta/llama-3.1-8b-instruct-fp8-fast` |
   | `WEB_APP_URL` | your WEB_URL from step 6 (links in intro emails; add it after step 6) |

6. **Create Web Service**. The first build takes several minutes. When the log says
   "Your service is live", copy the URL at the top (e.g.
   `https://skillbuddy-api.onrender.com`); save it as **API_URL**.
7. Check it: open `API_URL/api/v1/health` in a browser. It should show `"status":"ok"`.
8. **Settings** → **Build & Deploy** → **Auto-Deploy** → **After CI Checks Pass** → **Save**.

## Step 5. Scheduler: Cloudflare Worker with cron triggers

The API has no cron; this Worker calls `POST /api/v1/admin/jobs/tick` 17 times a day (hourly
08:00–23:00 IST, and 06:00 IST). The script is `infra/cloudflare-tick/worker.js`.

1. **https://dash.cloudflare.com** → left **Workers & Pages** (under Compute) → **Create** →
   **Create Worker** (Start with **Hello World**) → Name `skill-buddy-tick` → **Deploy**.
2. **Edit code** → select all the code in the editor and delete it → open
   **https://github.com/gsengh24/SkillBuddy/blob/main/infra/cloudflare-tick/worker.js** →
   **Copy raw file** (the copy icon) → paste into the editor → **Deploy**.
3. Back on the Worker → **Settings** → **Variables and Secrets** → **+ Add**:
   - Type **Text**, Name `API_URL`, Value = your API_URL (no trailing slash) → **Deploy**.
   - **+ Add** again: Type **Secret**, Name `JOBS_TICK_TOKEN`, Value = your JOBS_TICK_TOKEN
     (exactly the value given to Render) → **Deploy**.
4. **Settings** → **Trigger Events** → **+ Add** → **Cron Triggers** → enter the expression
   `30 2-17 * * *` → **Add**. Add a second one: `30 0 * * *` → **Add**.
5. **Settings** → **Observability** → turn **Workers Logs** on (free).
6. Check it: wait for the next half past the hour (UTC), then Worker → **Logs**. You
   should see `tick ok: enqueued=...`. A line with `HTTP 403` means the two
   JOBS_TICK_TOKEN values differ; `HTTP 404` means `JOBS_TICK_TOKEN` is missing on Render.

## Step 6. Web app on Vercel Hobby

1. **https://vercel.com/signup** → **Hobby** → **Continue with GitHub** (no card).
2. **Add New…** → **Project** → import **gsengh24/SkillBuddy** → **Root Directory** → **Edit**
   → `frontend` → **Continue**. Framework: Next.js (detected).
3. **Environment Variables**: Key `API_INTERNAL_URL`, Value = your API_URL → **Add**.
4. **Deploy**. When done, copy the domain shown (e.g. `https://skillbuddy.vercel.app`);
   save it as **WEB_URL**.
5. Back in Render → your API → **Environment** → edit `CORS_ALLOW_ORIGINS` → the Vercel
   domain (no trailing slash) → **Save, rebuild and deploy**.
6. Optional: Vercel project → **Settings** → **Deployment Protection** → **Vercel
   Authentication** on, to keep staging private.

## Step 6b. Google sign-in (OAuth client)

Optional. Without it, the sign-in page shows email codes only. "Continue with Google" accepts
only accounts on `ALLOWED_EMAIL_DOMAINS` (ADR 0011). Use a **separate** Google Cloud project
from the Gmail sender in step 2: the consent screen people see then names the app and asks for
nothing beyond their basic profile.

**Is Google's verification needed?** As of 2026-10-02, Google's documentation says no for an
app asking only for `openid`, `email` and `profile`: these are non-sensitive scopes. Google's
review is required for sensitive or restricted scopes, and brand verification only if you
upload a logo or want the app's branding shown. So:
- don't upload a logo;
- keep to these three scopes;
- re-check the Google Auth Platform's **Verification Center** page when you do this step.

1. **Project.**
   - Open **https://console.cloud.google.com**, signed in with your own Google account (not
     the sending Gmail).
   - Click the project picker at the top → **New Project** → name `skillbuddy-signin` →
     **Create** → select it.
   - Never add billing or a card; nothing here needs it.
2. **Consent screen.**
   - Menu ☰ → **Google Auth Platform** → **Get started**.
   - App name: the platform name (today `Skill Buddy`). User support email: yours → **Next**.
   - **Audience: External** → **Next**. (Internal is only possible for a Workspace you
     administer; Thapar's isn't yours.)
   - Contact email: yours → **Next** → tick the policy agreement → **Continue** → **Create**.
3. **Branding.**
   - Left menu **Branding**. Leave **App logo** empty.
   - Application home page: `WEB_URL` (from step 6).
   - Privacy policy link: `WEB_URL/privacy`. Terms of service link: `WEB_URL/terms`.
   - Under **Authorized domains** add the host of `WEB_URL` without `https://` (for example
     `skillbuddy.vercel.app`) → **Save**.
4. **Scopes.**
   - Left menu **Data Access** → **Add or remove scopes**.
   - Tick only `openid`, `.../auth/userinfo.email` and `.../auth/userinfo.profile` →
     **Update** → **Save**.
   - Add nothing else.
5. **Publish.** Left menu **Audience** → **Publish app** → **Confirm**. **Publishing status**
   must read **In production**. In "Testing" only listed test users can sign in.
6. **Client.**
   - Left menu **Clients** → **Create client** → Application type **Web application** →
     name `skillbuddy-web`.
   - Under **Authorized JavaScript origins** add nothing.
   - Under **Authorized redirect URIs**, **Add URI**, exactly:
     - staging: `WEB_URL/api/v1/auth/google/callback` (for example
       `https://skillbuddy.vercel.app/api/v1/auth/google/callback`);
     - production, when it exists: `https://<production domain>/api/v1/auth/google/callback`.
       You can add it later on the same client.
   - Click **Create**. Copy the **Client ID** and save it as **GOOGLE_OAUTH_CLIENT_ID**.
   - Copy the **Client secret** and save it as **GOOGLE_OAUTH_CLIENT_SECRET** in your
     password manager. It is shown in full only now; never paste it anywhere but Render.
7. **Render.** Open your API service → **Environment** → add:

   | Key | Value |
   | --- | --- |
   | `ALLOWED_EMAIL_DOMAINS` | `thapar.edu` |
   | `ALLOWED_EMAILS` | your own address(es), comma-separated, if you sign in with email codes from outside thapar.edu (optional) |
   | `BLOCKED_EMAILS` | leave empty for now |
   | `GOOGLE_SIGNIN_ENABLED` | `true` |
   | `GOOGLE_OAUTH_CLIENT_ID` | your GOOGLE_OAUTH_CLIENT_ID |
   | `GOOGLE_OAUTH_CLIENT_SECRET` | your GOOGLE_OAUTH_CLIENT_SECRET |
   | `GOOGLE_OAUTH_REDIRECT_URI` | `WEB_URL/api/v1/auth/google/callback` (identical to the client's redirect URI) |

   Then **Save, rebuild, and deploy**.

   > **Note:** `ALLOWED_EMAIL_DOMAINS` applies to email codes too. After this, only
   > `@thapar.edu` addresses and the ones on `ALLOWED_EMAILS` can sign in at all.
8. **Test with a real @thapar.edu account early** (pre-launch checklist).
   - Open `WEB_URL/login`, tick both boxes, choose **Continue with Google**, and pick a
     college account. You should land signed in.
   - If Google says **"Access blocked: … has not been approved by your administrator"**,
     Thapar's Workspace restricts third-party apps. Ask college IT to allow the client ID
     from step 6, or to allow apps that "only request basic info needed for Sign in with
     Google". Meanwhile email codes still work.
   - If you land on `/login?error=google_failed`, check the API logs for
     `google_sign_in_rejected` and its `reason`.

## Step 7. First sign-in

1. Open the Vercel domain → **Sign in or create an account** → your own email → tick both
   boxes → **Email me a code**. The first request after an idle period waits about a
   minute while Render wakes.
2. The email comes from GMAIL_SENDER. If it does not arrive within 2 minutes: Render →
   **Logs**, search `gmail_token_failed` (wrong client id, secret or token) or
   `email_send_failed`.
3. Enter the code. You land on the home page.

## Step 8. Deliverability to @thapar.edu (pre-launch checklist item 8)

1. Ask 3–5 volunteer students (with their consent) to sign in with their @thapar.edu
   address. Each tells you: inbox, spam/junk, or nothing.
2. On one received message: Gmail → **⋮** → **Show original** (Outlook: **…** → **View** →
   **View message details**). Confirm `spf=pass`, `dkim=pass`, `dmarc=pass`.
3. If messages go to quarantine or junk, ask college IT to allow-list GMAIL_SENDER.

## Step 9. Day-8 check (blocking, ADR 0008)

Eight or more days after the refresh token was created (step 2e.6), sign in again on
staging with any address. The code must arrive. If it does not and Render's logs show
`gmail_token_failed` with `invalid_grant`, the OAuth app was still in Testing: publish it
(step 2c.4), create a new refresh token (step 2e), update `GMAIL_REFRESH_TOKEN` in Render,
and wait another 8 days. Record the date of the passing check in the pre-launch checklist.

## Free-tier limits and catches (as of 2026-10-01)

| Service | Free allowance | Catches |
| --- | --- | --- |
| Vercel Hobby | 1M function calls, 4 active CPU-hours, 100 GB transfer a month | Non-commercial use only; over a limit pauses the feature for 30 days; 1 hour of logs |
| Render Free | 512 MB RAM, shared CPU, 750 instance-hours a month per workspace | Sleeps after 15 min without traffic (about 1 min to wake); **no outbound SMTP**; no shell or pre-deploy step (migrations run from GitHub Actions) |
| Neon Free | 100 CU-hours/month; storage 0.5 GB (the pricing page now says 1 GB; re-check); suspends after 5 min idle | Out of CU-hours or egress suspends the DB until next month; at 0.25 CU that is about 13 active hours a day; health checks must not hit `/health/ready` |
| Cloudflare Workers Free | 100,000 requests/day, 5 cron triggers per account | If the Worker stops, scheduled jobs stop (watch its Logs) |
| Gmail (personal) | 500 recipients per rolling 24 h; we cap at 450 | OAuth app must be In production; Google may limit accounts that look like bulk mail |
| Groq / Cloudflare Workers AI | See [free-tier-limits.md](free-tier-limits.md) | Optional; templates are used when absent or exhausted |

Koyeb Free is no longer an option (new accounts need a card since February 2026).

## Day-to-day

- **Logs:** Render → **Logs** (API and jobs). Vercel → **Logs** (1 hour on Hobby).
  Cloudflare Worker → **Logs** (ticks).
- **Migrations:** when a merged PR adds a file under `backend/migrations/versions/`, run
  **Actions → Migrate staging** before or right after Render deploys it.
- **Rollback:** Render → **Events** → earlier deploy → **Rollback**; Vercel → **Deployments**
  → earlier deployment → **Instant Rollback**. Rollbacks do not undo migrations; revert a
  migration with a new PR.
- **Watch the meters weekly:** Neon → **Monitoring** → compute hours (act if over 70% before
  day 21 of the month, ADR 0008); Render instance hours; `GET API_URL/api/v1/admin/storage`.
- **Optional admin token:** add `ADMIN_API_TOKEN` (32+ random characters, made like
  JOBS_TICK_TOKEN) in Render to enable `/api/v1/admin/storage`; send it as `X-Admin-Token`.

## When to move off this plan

Move to paid hosting (new ADR) before any commercial use (Vercel Hobby terms), when the
campus outgrows Neon's 100 CU-hours, or when cold starts get in the way.
