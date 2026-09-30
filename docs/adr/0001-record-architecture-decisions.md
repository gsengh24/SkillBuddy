# 1. Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-10-01

## Context

This is a long-lived product built by a small team with heavy use of AI-assisted coding.
Decisions about structure, dependencies and trade-offs are made quickly and then forgotten;
months later nobody, human or AI, can tell whether a choice was deliberate or accidental,
or whether it is still safe to change.

`docs/ARCHITECTURE.md` describes the target system, but it is a plan, not a history. It does
not record *why* one option was chosen over another at the moment the choice was made.

## Decision

We record every architecturally significant decision as an Architecture Decision Record
(ADR), following Michael Nygard's format, in `docs/adr/`.

- One decision per file, named `NNNN-short-title.md`, numbered sequentially and never reused.
- Each ADR has: Status, Date, Context, Decision, Consequences.
- Status is one of *Proposed*, *Accepted*, *Deprecated* or *Superseded by ADR-NNNN*.
- ADRs are immutable once accepted. To change a decision, write a new ADR that supersedes
  the old one and update only the old one's Status line.
- An ADR is added in the same pull request as the change it justifies.

"Architecturally significant" means: hard to reverse, affects more than one module, adds or
replaces an infrastructure component or major dependency, or changes a cross-cutting rule
(security, data retention, AI usage, API contracts).

## Consequences

- New contributors and AI assistants can read the reasoning behind the codebase in minutes.
- Reversing a decision requires engaging with the original reasons, which reduces churn.
- Writing an ADR adds a small cost to significant changes; this is intended.
- `CLAUDE.md` points to this directory so AI assistants consult it before proposing
  structural changes.
