# Free-tier limits

Living record of every external service we use, on its free tier (see the zero-cost
constraint, [ADR 0004](adr/0004-zero-cost-constraint.md)). Providers change their limits
without notice: re-check the source before relying on a row, and update the date.

**Adding a service:** check its current free tier first, then add a row with the plan,
limits, catches (sleeping, size caps, rate limits, data-use terms, card requirement) and
the date checked. If it needs a credit card, it cannot be used.

| Service | Plan | Limits | Catches | Checked |
| --- | --- | --- | --- | --- |
| GitHub Actions | Free, public repository | Standard GitHub-hosted runners are free for public repos. Up to 20 concurrent jobs; 6 hours per job. Cache: 10 GB per repository. (Private repos would get only 2,000 minutes and 500 MB artifact storage per month.) | Free only while the repo is **public**; making it private switches to the 2,000-minute quota, after which runs are blocked (no payment method). Larger runners are always billed; never use them. | 2026-10-01 |
| GitHub Codespaces | GitHub Free personal account | 120 core-hours and 15 GB-month storage per month. A 2-core machine (our devcontainer's 8 GB size) uses 2 core-hours per hour, so about **60 hours/month**. Idle timeout 30 min by default (5–240 min allowed). | Usage is **blocked** for the rest of the month once the quota is used (no payment method). Stopped codespaces and prebuilds still use storage; delete old codespaces. Prebuilds would also use Actions minutes and storage, so we don't use them. | 2026-10-01 |
| Groq API (AI gateway, primary LLM; [ADR 0007](adr/0007-ai-gateway.md)) | Free plan | Per model, per organisation: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b` each **30 requests/min, 1,000 requests/day, 8K tokens/min, 200K tokens/day**. Over a limit returns 429 with `retry-after`. Exact limits for our account are on the console's Limits page. | **Data use:** the Services Agreement (modified 2026-06-22) forbids Groq from training on inputs or outputs; no retention by default, logs up to 30 days for abuse and troubleshooting; turn on **Zero Data Retention** (Data Controls) before real data. Terms say "not for consumer use" (we are the customer). Free-service liability capped at $5,000. No SLA. Reasoning tokens of `gpt-oss` count towards limits. No card needed. | 2026-10-01 |
| Cloudflare Workers AI (AI gateway, secondary LLM and embedding fallback; ADR 0007) | Workers Free | **10,000 neurons/day**, reset 00:00 UTC (paid rate would be $0.011 per 1,000 neurons; not used). `@cf/openai/gpt-oss-20b`: 18,182 neurons per M input tokens, 27,273 per M output. `@cf/meta/llama-3.1-8b-instruct-fp8-fast`: 4,119 / 34,868. `@cf/baai/bge-small-en-v1.5`: 1,841 per M input tokens. | **Data use:** Cloudflare does not use Customer Content to train AI models or improve services. A match call (about 2,800 in + 700 out) costs about 70 neurons, so about 130 calls/day. Over the allowance, requests fail until the reset (no card, so no overage). No SLA. No card needed. | 2026-10-01 |
| Cloudflare Workers (job scheduler; [ADR 0008](adr/0008-free-runtime-jobs-and-email.md)) | Workers Free | 100,000 requests/day (reset 00:00 UTC); **5 Cron Triggers per account**, 1-minute granularity; 10 ms CPU per invocation, 15 min wall time for cron runs (waiting on `fetch` is not CPU). | Used only to call the API's tick endpoint 17 times a day. If the Worker stops, scheduled jobs stop: watch the last-tick time. Free Services may be discontinued at any time and carry no liability. No card needed. | 2026-10-01 |
| Gmail API (email sending; ADR 0008) | Personal Google account + Google Cloud project (no billing) | **500 recipients per rolling 24 hours** for a personal account; counted per recipient; over the limit, sending stops until the window clears. We cap at 450 (`EMAIL_DAILY_CAP`). | OAuth app must be published "In production" (in "Testing", refresh tokens for `gmail.send` expire after 7 days). Sender is a `gmail.com` address. Google may limit accounts that look like bulk mail. SMTP with an app password is not an option because Render Free blocks SMTP ports. No billing account needed (Google's documented behaviour; not tested here). | 2026-10-01 |
| Dependabot | Free (all repositories) | Version and security updates run on standard runners and do not count towards Actions minutes. We cap open PRs at 5 per ecosystem in `.github/dependabot.yml`. | Each Dependabot PR triggers our full CI run. Keep the open-PR limit low and group minor/patch updates. Dependabot on larger runners would be billed. | 2026-10-01 |

**Evaluated for the AI gateway and rejected** (details in ADR 0007, checked 2026-10-01):
Google Gemini API free tier (uses content to improve products, with human review, and
cannot be turned off outside the EEA, Switzerland and the UK; bars services likely used by
under-18s); Mistral La Plateforme Experiment plan (trains on free-tier input by default;
opt-out availability on the free plan unconfirmed; phone verification); Cerebras (payment
method required for the trial); OpenRouter `:free` models (50 requests/day without buying
credits with a card; upstream data policies vary); GitHub Models (retired 2026-07-30);
Hugging Face Spaces (Gradio, Docker and CPU Spaces need a paid plan; free ZeroGPU is
5 GPU-minutes/day, Gradio only).

**Evaluated for jobs, scheduling and email, and rejected** (details in ADR 0008, checked
2026-10-01):
- Scheduled GitHub Actions as a job runner: the terms forbid "part of a serverless
  application"; schedules can be delayed or dropped, and are disabled after 60 days without
  activity.
- Koyeb: a card is required for new accounts since February 2026.
- Fly.io: no free allowance.
- Railway: $1/month of credit.
- Upstash: no longer needed. Free databases are archived after 30 idle days, and Arq
  polling exceeds the command quota.
- Render Key Value Free: not persisted to disk.
- Brevo and Resend: need an authenticated domain to reach other people's inboxes; we own
  none yet.
- MailerSend and Amazon SES: card.

Planned staging providers (Vercel Hobby, Render Free / Koyeb Free, Neon Free, Upstash Free)
are evaluated in [deployment-plan.md](deployment-plan.md); add each here when it is
actually adopted.

**Sources:** GitHub Docs: Actions billing and limits, Codespaces billing and timeout
settings, Dependabot on GitHub Actions runners. Groq: docs "Rate limits" and Services
Agreement. Cloudflare: Workers AI "Pricing" and Workers AI privacy docs. Google: Gemini API
Additional Terms. Mistral: commercial terms and Help Center (privacy settings). Hugging
Face: Spaces overview and ZeroGPU docs.
