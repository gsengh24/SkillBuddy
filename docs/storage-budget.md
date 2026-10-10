# Database storage budget

Part of the zero-cost constraint ([ADR 0004](adr/0004-zero-cost-constraint.md)). The rules
that every task must follow are in [CLAUDE.md](../CLAUDE.md#storage-rules); this document
holds the numbers behind them.

## The limit

| Item | Value |
| --- | --- |
| Planned free Postgres host | Neon Free ([deployment-plan.md](deployment-plan.md)) |
| Storage limit | **0.5 GB per project** (checked 2026-10-01) |
| When exceeded | Writes are blocked; data is not deleted |
| Target budget | **Stay under 70% = 350 MB** |
| Warning threshold | 70% (350 MB): warn admins |
| Protect threshold | 90% (450 MB): pause new signups and non-essential writes |

Neon's pricing page does not say whether the 0.5 GB counts only table data or also its
point-in-time history (which has its own 1 GB cap). Use the size Neon's dashboard reports
as the source of truth, alongside `pg_database_size()`.

## Per-user estimate

> **These are estimates, not measurements.** They are calculated from column sizes, typical
> PostgreSQL overheads (~28 bytes per row, ~40–60 bytes per B-tree index entry) and the
> assumptions listed. Replace them with measured numbers (`pg_total_relation_size` per table
> divided by user count) as soon as staging has synthetic data.

Assumptions: text caps as in the storage rules (profile text 2,000 characters, messages
2,000 characters); 4 embedding facets per user; HNSW index roughly 1.2× the raw vector
data; events kept raw for 30 days.

| Table | What is stored per user | Assumption | Per user (384-dim) | Per user (768-dim) |
| --- | --- | --- | --- | --- |
| `users` | 1 row + primary key and unique email index (+ consent and deletion columns, migration 0002) | ~200 B row | ~0.3 KB | ~0.3 KB |
| `auth_identities` | 1 email identity (Google later) + unique (provider, subject) index | ~150 B | ~0.3 KB | ~0.3 KB |
| `profiles` | About text (capped at 2,000 characters), structured JSON, timezone, languages; display name, up to 3 links, parse state and AI-consent columns (migration 0005, ~0.2 KB) | ~2 KB text + ~1.5 KB JSON + ~0.2 KB | ~4 KB | ~4 KB |
| `profile_embeddings` | 4 vectors + HNSW index + unique index | 4 × (vector + ~120 B row) × 2.2 | ~14 KB | ~28 KB |
| `events` | Behavioural log, raw 30 days | 5 events/day × 30 days × ~200 B | ~30 KB | ~30 KB |
| `messages` | Chat messages (body up to 2,000 characters; sender stored as one flag, not a user id), plus two read times on each connection (migration 0009, [ADR 0012](adr/0012-chat-delivery-by-polling.md)) | Deleted `MESSAGE_RETENTION_DAYS` (90) after sending; about 100 kept per user at a time × ~300 B, plus ~60 B of index each | ~36 KB | ~36 KB |
| `sessions` + `otp_codes` | Active sessions (max 90 days); codes purged once expired | 2 sessions × ~300 B | ~0.6 KB | ~0.6 KB |
| `auth_events` | Logins, failures | 20 in the retention window × ~200 B | ~4 KB | ~4 KB |
| `match_requests` + `matches` | Match requests (text up to 1,000 characters, parsed JSON) and up to 5 matches each, with reasons (migration 0007) | About 1 request a week kept for 90 days (`MATCH_REQUEST_RETENTION_DAYS`): 13 × (1.2 KB + 5 × 0.4 KB) | ~42 KB | ~42 KB |
| `intros` + `connections` + `notifications` | Intros (note up to 500 characters), connections, in-app notifications (migration 0008) | A few intros and about 20 notifications per 90 days; notifications purged after `NOTIFICATION_RETENTION_DAYS` (90) | ~6 KB | ~6 KB |
| `space_goals` + `space_skills` + `progress_logs` | Pair spaces (migration 0014, [ADR 0013](adr/0013-pair-spaces-v1.md)): shared goals (title up to 120 characters), skills to grow (up to 60) and progress notes (up to 500), keyed by the connection | Notes deleted 90 days after writing; the whole space 90 days after its connection ends (`SPACE_RETENTION_DAYS`); at most 30 goals and 10 skills per person per space | ~3 KB | ~3 KB |
| `teams` + `team_members` + `team_invites` | Teams (migration 0026, [ADR 0016](adr/0016-teams.md)): name (up to 60 characters), purpose, description (up to 300); one row per member; one per invite | A closed team is deleted `TEAM_RETENTION_DAYS` (90) after closing; invites expire after 14 days and are deleted 90 days later; at most 5 teams per person, 6 people per team, 20 open invites per team | ~2 KB | ~2 KB |
| **Total** | | | **~143 KB** | **~156 KB** |

Tables that do not grow per user (migration 0003, [ADR 0008](adr/0008-free-runtime-jobs-and-email.md)):

| Table | What is stored | Retention | Estimated size |
| --- | --- | --- | --- |
| `jobs` | One row per background job (IDs only, no personal data), about 300 B | Succeeded: 7 days; dead: 30 days; queued/running: until done | Under 1 MB at campus scale (a few thousand jobs a day) |
| `rate_limit_counters` | One row per key and window, about 150 B | Deleted hourly once the window has expired | A few KB |
| `email_log` | One row per email recipient: purpose, keyed hash, provider, time; about 150 B | 30 days | Under 2 MB (at most 450 emails a day) |
| `oauth_states` | One row per unfinished "Continue with Google" attempt: a keyed hash, the tick-box answers and the return path; about 200 B (migration 0006, [ADR 0011](adr/0011-google-sign-in.md)) | Deleted when used; unused rows purged daily after their 10-minute expiry | Under 1 MB |
| `blocks` | One row per block (two ids and a time, about 0.1 KB plus two index entries; migration 0011). Also `connections.ended_at` (8 B per connection) | Until the blocker unblocks or either account is deleted | Under 1 MB (people block rarely) |
| `moderation_actions` | Audit log: one row per resolve, suspend or unsuspend (ids, action, the moderator's note up to 500 characters); about 0.2 KB (migration 0013) | Deleted after `MODERATION_LOG_RETENTION_DAYS` (365) | Under 5 MB a year |
| `data_exports` | One row per "Download my data" request (migration 0017): status and times, about 0.2 KB; while the emailed link works, the gzipped JSON file too (typically 5 to 50 KB, at most a few hundred KB) | File dropped when the link expires (`DATA_EXPORT_LINK_HOURS`, 72); row deleted after `DATA_EXPORT_RETENTION_DAYS` (90). One request per person per 24 hours | Under 5 MB even if 100 people ask on the same day |
| `admin_accounts` + `admin_recovery_codes` + `admin_sessions` | Admin roles and encrypted two-step secrets, about 10 hashed recovery codes each, and short admin sessions (migration 0018, [ADR 0015](adr/0015-admin-portal.md)) | Deleted with the account; sessions purged daily once expired (30 idle minutes, 12 hours at most) | Under 100 KB (a handful of admins) |
| `admin_audit_log` | One row per admin action: ids, action, reason (10 to 500 characters), IP; about 1 KB | **Kept without a time limit**: append-only, a database trigger refuses UPDATE and DELETE | About 4 MB a year at 10 actions a day; review if it passes 20 MB |
| `admin_notes` + search indexes | Private admin notes on users (up to 1,000 characters, migration 0019), and trigram, intent and open-report indexes for the admin Users page | Notes deleted with the account. The indexes grow with users: about 0.3 KB per user | Notes under 1 MB; indexes about 30 MB at 100,000 users |
| `reports` | One row per report of a message, an intro or a profile: reason, note (up to 500 characters) and a frozen copy as JSON (a message and the 10 before it, an intro's request and note, or what a profile showed); about 0.5 KB plus a few KB of copy, at most about 22 KB (migrations 0010, 0012) | Open: until resolved. Resolved: deleted 180 days after resolving (`REPORT_RETENTION_DAYS`) | Under 5 MB (reports are rare) |
| `signup_applications` + `invite_codes` | Applications to join while signups are invite only (migration 0022): email, how they heard (a fixed choice), status and times, about 0.2 KB; one per address. Invite codes: code, limits and times, about 0.1 KB | Applications deleted 90 days after a decision, or 180 days after applying if never decided, with their one-use codes; shareable codes 180 days after they expire or are revoked | Under 2 MB even with 5,000 applications |
| `app_settings` + `signup_domains` | Admin settings by key (the signup mode) and allowed or blocked email domains, about 0.1 KB each (migration 0022) | Until an admin removes them; at most 200 domains per list | A few KB |
| `content_flags` | One row per content rule matched by a saved request, bio or intro note (migration 0023): rule, item id and status, about 0.1 KB; never the text. One open flag per rule and item | Deleted with the account; decided flags 90 days after the decision, open ones after 180 days | Under 2 MB (flags are rare) |
| `ai_calls` | One row per AI provider call (migration 0023): provider, kind, outcome, duration, cost; about 0.1 KB. No prompt, response or user | 30 days, removed as new calls are logged (at most hourly) | Under 3 MB at the daily AI call cap |
| `banners` | Admin announcements (migration 0024): message (at most 160 characters), type, times; about 0.3 KB | Deleted 90 days after they end | A few KB |
| `email_sends` | One row per email the app tries to send (migration 0024): address, template, delivered or failed, a short error, the job to retry it with; about 0.3 KB. Never the body | 30 days, removed as new emails are logged (at most hourly) | Under 4 MB at the daily email cap (450 a day) |
| `admin_exports` | One row per admin CSV export of the Users list or the audit log (migration 0025); the gzipped CSV (about 3 MB at 100,000 users) while its link works | File dropped 24 hours after it is ready; row deleted 30 days after it was asked for. One export of each kind at a time | Under 10 MB at any moment |

Chosen dimension: **384** (`BAAI/bge-small-en-v1.5`, [ADR 0007](adr/0007-ai-gateway.md)).
Migration 0004 changed the column from 768 to 384 (2026-10-02).

## What fits

Allowing ~20 MB for PostgreSQL's own catalog and empty-table overhead:

| Embedding dimension | Budget (350 MB) | Protect threshold (450 MB) |
| --- | --- | --- |
| 384 | about **2,400 users** | about 3,100 users |
| 768 | about 2,200 users | about 2,800 users |

Updated 2026-10-03 for match requests (migration 0007), intros and notifications (0008) and chat (0009); before them the budget fitted about
4,000 users. Match history, events and messages dominate, not embeddings. Shorter
`MATCH_REQUEST_RETENTION_DAYS` (for example 45 days halves the match share), shorter event
retention and a message history cap are the biggest levers if space gets tight. Shorter event retention (or aggregating
events into daily counts) and a message history cap are the biggest levers if space gets
tight.

## Monitoring and enforcement

- `GET /api/v1/admin/storage` (enabled when `ADMIN_API_TOKEN` is set; send it as
  `X-Admin-Token`) reports the database size, the limit, the percentage used, the status
  (`ok`, `warning` at 70%, `critical` at 90%) and the ten largest tables.
- At **90%** new sign-ups are refused with `503 signups_paused` ("try again later"); existing
  users can still sign in. Endpoints that perform non-essential writes add the
  `require_storage_capacity` dependency and refuse with `503 storage_full`.
- The limit and thresholds are settings: `DATABASE_SIZE_LIMIT_MB` (500),
  `STORAGE_WARN_PERCENT` (70), `STORAGE_PAUSE_PERCENT` (90).
- Retention jobs are enqueued by the scheduler's tick (`POST /api/v1/admin/jobs/tick`, ADR 0008):
  daily on the first tick of each UTC day, hard-deleting accounts past the 30-day grace
  period, purging expired codes and sessions, and pruning `auth_events` older than
  `AUTH_EVENT_RETENTION_DAYS` (90); hourly, purging the job-queue tables.

## Keeping it current

- When a migration adds a growing table, add a row here and state its retention and
  estimated growth in the PR description.
- Once the size monitor exists, record measured per-user figures and the date here.
