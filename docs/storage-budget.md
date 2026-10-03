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
| **Total** | | | **~138 KB** | **~151 KB** |

Tables that do not grow per user (migration 0003, [ADR 0008](adr/0008-free-runtime-jobs-and-email.md)):

| Table | What is stored | Retention | Estimated size |
| --- | --- | --- | --- |
| `jobs` | One row per background job (IDs only, no personal data), about 300 B | Succeeded: 7 days; dead: 30 days; queued/running: until done | Under 1 MB at campus scale (a few thousand jobs a day) |
| `rate_limit_counters` | One row per key and window, about 150 B | Deleted hourly once the window has expired | A few KB |
| `email_log` | One row per email recipient: purpose, keyed hash, provider, time; about 150 B | 30 days | Under 2 MB (at most 450 emails a day) |
| `oauth_states` | One row per unfinished "Continue with Google" attempt: a keyed hash, the tick-box answers and the return path; about 200 B (migration 0006, [ADR 0011](adr/0011-google-sign-in.md)) | Deleted when used; unused rows purged daily after their 10-minute expiry | Under 1 MB |
| `blocks` | One row per block (two ids and a time, about 0.1 KB plus two index entries; migration 0011). Also `connections.ended_at` (8 B per connection) | Until the blocker unblocks or either account is deleted | Under 1 MB (people block rarely) |
| `reports` | One row per report of a message, an intro or a profile: reason, note (up to 500 characters) and a frozen copy as JSON (a message and the 10 before it, an intro's request and note, or what a profile showed); about 0.5 KB plus a few KB of copy, at most about 22 KB (migrations 0010, 0012) | Open: until resolved. Resolved: deleted 180 days after resolving (`REPORT_RETENTION_DAYS`) | Under 5 MB (reports are rare) |

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
