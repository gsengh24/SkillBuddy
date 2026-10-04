# 13. Pair spaces v1: shared goals, skills to grow and progress logs

- **Status:** Accepted
- **Date:** 2026-10-04
- **Amends:** [ARCHITECTURE.md](../ARCHITECTURE.md) §5 (data model: `spaces / goals /
  skill_logs`) and §11 (Phase 5 deliverables)

## Context

ARCHITECTURE.md describes a "pair space": after two people connect, they can track a
project or a skill together. "Each person lists skills they want to grow, logs progress,
and sees the partner's." Phase 5 also lists reminders, conversation starters and project
templates. The web app's nav already shows "Pair spaces" as SOON and disabled.

The owner set the scope on 2026-10-04:

1. v1 is **shared goals, skills to grow and progress logs only**. Reminders, conversation
   starters and project templates come after launch.
2. When a connection ends, the space is **hidden from both people at once and deleted 90
   days later**. Progress log entries are **deleted 90 days after they are written**.
3. **Blocking closes the space for both people**, the same as chat.
4. Space entries (goal titles and log notes) are **reportable**, following the report target
   pattern from #50.
5. No reminders in v1.

The zero-cost constraints still apply: no new service, small rows, hard caps on writes, and
retention from day one (CLAUDE.md, storage rules).

## Decision

### One space per open connection, with no table of its own

A space is not a separate row. It **is** the connection: goals, skills and logs each carry a
`connection_id`. This keeps storage compact and makes the rules follow the connection
automatically:

- **Who can see it:** only the two people in the connection, exactly like chat. Anyone else
  gets "not found".
- **When it closes:** when the connection ends (a block sets `connections.ended_at`), the
  space disappears for both at once. Every space path asks `app/services/blocks.blocked_with`
  too, so a block closes it both ways even before the connection row is updated.
- **When it is deleted:** a daily job deletes the goals, skills and logs of connections that
  ended more than **90 days** ago. Account deletion removes the connection and everything on
  it (ON DELETE CASCADE).
- **A new intro after an unblock** starts a fresh connection (step 7a, #49), so it also
  starts an empty space; the old one is deleted with the old connection.

There is no "create a space" step: the space exists, empty, for every open connection.

### What a space holds

| Thing | Fields (user-written text capped) | Who can change it | Retention |
| --- | --- | --- | --- |
| **Goal** (shared) | title (≤ 120 characters), status `open` or `done`, optional due date, who added it | Either person: rename, mark done or open, set or clear the due date, delete | Until the connection ends, then 90 days |
| **Skill to grow** (each person's own) | name (≤ 60 characters), whose skill it is | Only its owner adds or removes it | Until the connection ends, then 90 days |
| **Progress log** | note (≤ 500 characters), optional link to one goal or one of the author's skills, who wrote it | Only its author deletes it | **90 days after it was written**, or sooner if the connection ends and 90 days pass |

The sender of each item is stored like chat messages: `from_a` (true when written by
`user_a`), not a user id. It is smaller and can never point at someone outside the pair.

### Limits (CLAUDE.md, zero-cost rule 5)

- At most **30 goals** and **10 skills per person** in a space at once.
- **`SPACE_WRITES_PER_DAY` (100)** per person: every add, edit and delete in spaces counts.
- Storage-guarded like other non-essential writes (`require_storage_capacity`).

### What spaces are not used for

- No AI reads space content, and it is not used for matching.
- No emails, notifications or reminders in v1.

### Reporting

Goal titles and log notes can be reported by the other person, with the same rules as
message reports: the report keeps a frozen copy (the entry's text and when it was written),
the moderator sees only that copy, and the reported person isn't told. This adds report
targets `goal` and `progress_log` to `reports.target`, so it needs a migration and **owner
review before merge** (step 9 rule). It is built after the space itself, together with the
privacy-page retention lines for spaces.

### API (exact shapes in the backend PR)

Under the connection, since the space is the connection:
`GET /api/v1/connections/{id}/space` (goals, skills and the newest logs), plus `POST`,
`PATCH` and `DELETE` for goals, skills and logs, and a cursor-paged log history.

## Consequences

**Positive**

- No new table for spaces, no new service, and the access rules are chat's rules, already
  tested (membership, blocks, ended connections).
- Retention is automatic and bounded: logs never outlive 90 days, and a finished connection
  leaves nothing behind after 90 days.
- Mobile-ready: plain REST under `/api/v1`.

**Negative / risks**

- A long-running pair loses log entries older than 90 days. Goals and skills stay while the
  connection is open, so the space keeps its shape, but the history is short. If people want
  longer history, that is a later retention decision (and a privacy-page change).
- Two people can edit the same goal at the same time; the last write wins. Acceptable for
  short titles and a done flag.

**Post-launch (not in v1):** reminders (in-app, possibly email within the non-login email
budget), conversation starters and project templates (Phase 5 in ARCHITECTURE.md).
