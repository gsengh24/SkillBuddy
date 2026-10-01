# 5. Valkey instead of Redis

- **Status:** Superseded by [ADR 0008](0008-free-runtime-jobs-and-email.md) (no Redis-compatible store; queue and rate
  limits move to PostgreSQL)
- **Date:** 2026-10-01

## Context

The dev stack, CI and the reference production layout used the `redis:7.4-alpine` image.
Redis 7.4 and later are released under RSALv2/SSPLv1: source-available, not an OSI open
source licence. The Phase 0 exit report flagged this against the zero-cost constraint
(ADR 0004), which prefers free tiers and open-source software.

We use Redis only through its protocol: Arq's job queue, rate-limit counters and cache.
Nothing depends on Redis-only features.

## Decision

Run **Valkey** (BSD-3-Clause, Linux Foundation fork of Redis 7.2) everywhere we run our own
key-value server: `docker-compose.yml`, `docker-compose.prod.yml` and the CI service
container, pinned to `valkey/valkey:9.1.2-alpine`. The Compose service is named `valkey`.

The client side is unchanged: the `redis` Python client, Arq and the `REDIS_URL` setting
all speak the Redis protocol, which Valkey implements. The variable names (`REDIS_URL`,
`REDIS_PORT`, `REDIS_PASSWORD`) and the readiness check name `redis` stay as they are,
because they describe the protocol, not the server.

Managed hosts may still offer Redis-protocol services (e.g. Upstash in the staging plan,
ADR 0003); any Redis-compatible server works.

## Consequences

- The self-hosted stack is fully open source.
- No code changes, no data migration (no persistent Redis data exists).
- Valkey and Redis may diverge in future; we stay on commands both support (basic
  strings, sorted sets and lists used by Arq).
- Dependabot tracks the Valkey image like any other.
