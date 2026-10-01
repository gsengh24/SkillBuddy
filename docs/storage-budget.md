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
| `profiles` | About text, structured JSON, timezone, languages | ~2 KB text + ~1.5 KB JSON | ~4 KB | ~4 KB |
| `profile_embeddings` | 4 vectors + HNSW index + unique index | 4 × (vector + ~120 B row) × 2.2 | ~14 KB | ~28 KB |
| `events` | Behavioural log, raw 30 days | 5 events/day × 30 days × ~200 B | ~30 KB | ~30 KB |
| `messages` | Chat messages sent | 100 retained messages × ~300 B | ~30 KB | ~30 KB |
| `sessions` + `otp_codes` | Active sessions (max 90 days); codes purged once expired | 2 sessions × ~300 B | ~0.6 KB | ~0.6 KB |
| `auth_events` | Logins, failures | 20 in the retention window × ~200 B | ~4 KB | ~4 KB |
| **Total** | | | **~84 KB** | **~97 KB** |

Chosen dimension: **384** (`BAAI/bge-small-en-v1.5`, [ADR 0007](adr/0007-ai-gateway.md)).
The current schema still uses 768 until migration 0003 changes it.

## What fits

Allowing ~20 MB for PostgreSQL's own catalog and empty-table overhead:

| Embedding dimension | Budget (350 MB) | Protect threshold (450 MB) |
| --- | --- | --- |
| 384 | about **4,000 users** | about 5,200 users |
| 768 | about 3,400 users | about 4,400 users |

Events and messages dominate, not embeddings. Shorter event retention (or aggregating
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
- The worker runs the retention jobs daily (03:00 and 03:30 UTC): hard-deleting accounts past
  the 30-day grace period, purging expired codes and sessions, and pruning `auth_events`
  older than `AUTH_EVENT_RETENTION_DAYS` (90).

## Keeping it current

- When a migration adds a growing table, add a row here and state its retention and
  estimated growth in the PR description.
- Once the size monitor exists, record measured per-user figures and the date here.
