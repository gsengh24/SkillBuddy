# 18. Pair spaces are teams: the one-to-one spaces are removed

- **Status:** Accepted
- **Date:** 2026-10-11
- **Amends:** [ADR 0013](0013-pair-spaces-v1.md) (pair spaces v1) and
  [ADR 0016](0016-teams.md) (teams: "pair spaces stay as they are")

## Context

ADR 0016 added teams beside the two-person pair spaces. The owner has now decided there
should be one feature, not two: keep only teams, and call them **pair spaces**.

## Decision

- The one-to-one pair space (goals, skills and notes hanging off a connection, under
  `/connections/{id}/space`) is **removed**: its pages, its API, its feature switch
  (`pair_spaces`) and its data.
- A **pair space is a team**: up to six people, a chat, shared goals, skills to grow and
  progress notes, four ways to join. Two people who want a space of just the two of them make
  a pair space and invite each other.
- **The rename is user-facing only.** Screens, notifications, legal wording, the admin
  Settings page and API error messages say "pair space". Code, tables, the `teams` feature
  switch and API paths (`/teams`, `/team-messages`) keep the name `teams`, so no API contract
  or table is renamed. The old `/spaces` address redirects to `/teams`.
- **Data.** Migration 0034 deletes every goal, skill and note that belonged to a connection,
  then drops `connection_id` and `from_a` from `space_goals`, `space_skills` and
  `progress_logs`, drops the "exactly one parent" CHECK, makes `team_id` and `author_id`
  required, and turns the partial team indexes into ordinary ones. The downgrade restores the
  columns and constraints but cannot restore the deleted rows.
- Goal and note reports keep working (`/space-goals/{id}/report`, `/progress-logs/{id}/report`)
  and now cover pair-space members only. Reports already filed about old two-person entries
  keep their frozen copy.
- The `teams` feature switch is the single switch for pair spaces. It stays **off by default**
  until the owner turns it on in admin Settings; a stored `feature:pair_spaces` row is ignored.
- The Home summary strip's third cell counts **connections** instead of one pair space per
  connection.

## Consequences

- Until the owner turns the `teams` switch on, there is no space feature at all.
- Privacy and terms wording changes (one pair-space description instead of two), so this
  stops for the owner's review.
- Storage shrinks (two columns per table; the old rows are gone). Retention is unchanged:
  notes 90 days after writing, a closed pair space 90 days after closing.
