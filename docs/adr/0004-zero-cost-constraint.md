# 4. Zero-cost constraint

- **Status:** Accepted; decision 2 partly superseded by [ADR 0007](0007-ai-gateway.md) (the LLM
  is a core pipeline stage, used by default; the no-LLM path is a fallback only)
- **Date:** 2026-10-01

## Context

The owner will not spend money on this project in the near future. ADR 0003 already moved
staging onto free tiers, but the constraint is wider than hosting: it affects which
services and libraries we may adopt, how the AI layer is designed, how much CI runs, and
what happens when a free limit runs out.

`docs/ARCHITECTURE.md` assumes hosted LLMs and embedding models with per-request cost, and
paid infrastructure as the product grows. Those parts of the plan are deferred while this
constraint holds; the plan itself is not rewritten.

## Decision

Everything runs on **free tiers or open-source software, with no credit card required**.

1. **No paid services or paid-only dependencies**, and nothing that needs a card on file.
   Before adopting an external service or API, check its current free tier and record its
   limits and catches (sleeping, size caps, rate limits, data-use terms), with the date
   checked, in `docs/free-tier-limits.md`.
2. **AI gateway with three modes** (designed in the Phase 1 AI-gateway ADR):
   - embeddings from an **open-source model running locally on CPU**;
   - an **optional free-tier LLM provider**;
   - a **"no LLM" mode**.
   The matching pipeline must work end to end with no LLM call: rule-based scoring and
   template explanations. An LLM, when available, only improves quality.
3. **Configurable embedding dimension.** The current schema stores `vector(768)`
   (`EMBEDDING_DIMENSIONS` in `app/models/profile_embedding.py` and the initial migration).
   Small CPU-friendly models often use fewer dimensions (for example 384). The dimension
   becomes a setting and the schema is revisited in the Phase 1 AI-gateway ADR, **before any
   real data exists**, so changing it needs only a migration, not a data backfill.
4. **No real user data to free APIs that may train on inputs.** If a provider's terms allow
   training on submitted data, only synthetic data may be sent to it. Development and
   evaluation use synthetic profiles.
5. **Hard usage caps and graceful failure.** Every feature that consumes a limited resource
   has an explicit cap. When a cap or a provider's free limit is hit, the user gets a clear
   "try again later" response (our standard error envelope), never an unbounded bill or a
   crash.
6. **Cheap CI.** Cache dependencies, run the full pipeline only on pull requests and
   `main`, and keep Dependabot's open-PR limit low.
7. **Small footprint.** Prefer slim Docker images and low memory use; free hosts offer
   roughly 256–512 MB of RAM.

## Consequences

**Positive**

- No financial risk; nothing can generate a bill.
- The product works without any external AI provider, so outages, quota exhaustion or
  terms changes degrade quality rather than break matching.
- Synthetic-data-only evaluation keeps personal data away from third parties.

**Negative / risks**

- Lower match quality without a strong LLM; template explanations are less personal than
  LLM-written ones.
- A local embedding model needs CPU and RAM in the worker or API, which competes with free
  hosts' small memory limits. Model choice must account for this.
- Free tiers change or disappear without notice, so `docs/free-tier-limits.md` must be
  re-checked before relying on it, and features must keep working when a limit is hit.
- Some ARCHITECTURE.md goals (always-on worker, managed backups, observability tooling)
  wait until the constraint is lifted.

**When to revisit**

When there is a budget, or before public launch. Lifting the constraint needs a new ADR
that supersedes this one.
