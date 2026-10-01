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
| `users` | 1 row + primary key and unique email index | ~150 B row | ~0.3 KB | ~0.3 KB |
| `profiles` | About text, structured JSON, timezone, languages | ~2 KB text + ~1.5 KB JSON | ~4 KB | ~4 KB |
| `profile_embeddings` | 4 vectors + HNSW index + unique index | 4 × (vector + ~120 B row) × 2.2 | ~14 KB | ~28 KB |
| `events` | Behavioural log, raw 30 days | 5 events/day × 30 days × ~200 B | ~30 KB | ~30 KB |
| `messages` | Chat messages sent | 100 retained messages × ~300 B | ~30 KB | ~30 KB |
| `sessions` + OTP codes | Active sessions; codes purged daily | 2 sessions × ~250 B | ~0.5 KB | ~0.5 KB |
| `auth_events` | Logins, failures | 20 in the retention window × ~200 B | ~4 KB | ~4 KB |
| **Total** | | | **~83 KB** | **~97 KB** |

Planned dimension: **384** (a small open-source CPU model; the final choice is made in the
Phase 1 AI-gateway ADR). The current schema uses 768.

## What fits

Allowing ~20 MB for PostgreSQL's own catalog and empty-table overhead:

| Embedding dimension | Budget (350 MB) | Protect threshold (450 MB) |
| --- | --- | --- |
| 384 | about **4,000 users** | about 5,200 users |
| 768 | about 3,400 users | about 4,400 users |

Events and messages dominate, not embeddings. Shorter event retention (or aggregating
events into daily counts) and a message history cap are the biggest levers if space gets
tight.

## Keeping it current

- When a migration adds a growing table, add a row here and state its retention and
  estimated growth in the PR description.
- Once the size monitor exists, record measured per-user figures and the date here.
