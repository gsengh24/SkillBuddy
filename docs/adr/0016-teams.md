# 16. Teams: groups of up to six, with four ways to join and a team chat

- **Status:** Proposed (the owner's merge of this PR accepts it; the first code PR sets it
  to Accepted)
- **Date:** 2026-10-10
- **Amends:** [ARCHITECTURE.md](../ARCHITECTURE.md) §5 (data model), §6 (modules) and §11
  (roadmap). Extends [ADR 0012](0012-chat-delivery-by-polling.md) (chat) and
  [ADR 0013](0013-pair-spaces-v1.md) (pair spaces) to groups; neither is replaced.

## Context

Everything after a match is built for exactly two people: a connection is a pair
(`user_a < user_b`), chat messages and pair-space entries hang off the connection, and the
author of each is one flag (`from_a`). Hackathons and projects need more than two people.

The owner set the scope on 2026-10-10:

1. Add **teams**: groups made for a hackathon, a project or any other purpose.
2. **Pair spaces stay** as they are; teams are a second feature beside them.
3. A team holds **up to 6 people**.
4. A team has what a pair space has (shared goals, skills to grow, progress notes) **plus a
   team chat**.
5. **All four ways to join** are wanted: inviting a connection, an invite link, open teams
   people ask to join, and the matcher finding teammates.

The zero-cost and storage rules still apply (CLAUDE.md): no new service, capped text, hard
caps on writes, retention from day one.

## Decision

### Data model

Unlike a pair space, a team needs rows of its own: it has a name, an owner and members who
come and go.

| Table | Holds | Notes |
| --- | --- | --- |
| `teams` | name (≤ 60 characters), purpose (`hackathon`, `project`, `study`, `other`), description (≤ 300), owner, `listed` flag, "looking for" text (≤ 200, shown only when listed), invite-link hash and expiry, `closed_at` | The invite code itself is never stored, only a keyed hash, like sign-in codes |
| `team_members` | team, person, `joined_at`, `read_at` (team chat read state) | Unique per team and person; at most 6 rows per team, checked under a row lock on the team |
| `team_invites` | team, person, kind (`invite`, `request`, `suggested`), status (`pending`, `accepted`, `declined`, `withdrawn`, `expired`), note (≤ 300), `expires_at` | One table for all three "waiting for a yes" cases; one pending row per team and person |
| `team_messages` | team, sender (a user id), body (same cap as chat), `created_at` | A group has more than two people, so the `from_a` flag cannot be used |

**Goals, skills and progress notes reuse the pair-space tables.** `space_goals`,
`space_skills` and `progress_logs` each get a nullable `team_id` and a nullable `author_id`,
`connection_id` becomes nullable, and a `CHECK` requires exactly one of `connection_id`
(with `from_a`) or `team_id` (with `author_id`). The same limits, the same retention job and
the existing report targets (`goal`, `progress_log`) then cover both. Three duplicate tables
were the alternative; rejected as unused duplication (storage rule 4).

`match_requests` gets a nullable `team_id` (see "The matcher finds teammates").

### Roles

One **owner** and **members**. The owner renames the team, edits its description, lists or
unlists it, makes or resets the invite link, invites, answers join requests, removes members
and closes the team. Members read and write everything inside and can leave. When the owner
leaves, the longest-standing member becomes the owner; when the last person leaves, the team
closes.

### Four ways to join

Every route ends with the person joining saying yes themselves, and with the owner having
opened that route. No one is ever added to a team without their own action.

1. **Invite a connection.** The owner invites someone they have an open connection with.
   The person accepts or declines (a `team_invites` row, kind `invite`). Built first: it
   reuses consent and blocks exactly as they work today.
2. **Invite link.** The owner makes a link (a random code; expires after 7 days; can be
   reset, which kills the old one). A signed-in person who opens it sees the team's name,
   purpose and size and chooses to join. The link stops working when the team is full.
3. **Open teams.** An owner can **list** a team with a "looking for" line. Signed-in people
   browse listed teams (cursor-paged, filter by purpose) and **ask to join** with a short
   note (kind `request`); the owner accepts or declines. A decline is not shown to the
   asker, like intros: it looks pending until it expires.
4. **The matcher finds teammates.** The owner writes what teammate the team needs. That is
   an ordinary match request with `team_id` set, so it runs through the existing pipeline
   (AI gateway, LLM-first with the rule-based fallback, daily caps, redaction: ADR 0007)
   and counts against `MATCH_REQUESTS_PER_DAY`. People already in the team are filtered
   out. On a match, the action is "Invite to team" instead of "Send intro" (kind
   `suggested`); the candidate sees the reason and the team's name, purpose and size, and
   accepts or declines. No AI reads team chat, goals or notes.

**Consent, stated plainly.** Routes 2, 3 and 4 put people in one chat who have no
connection with each other. The person joining agrees by joining; the owner agrees by
opening the route; **the other members do not agree one by one**. They see who joined (an
in-app notification and a line in the team), and can leave, block or report. This is a
deliberate loosening of "contact requires two-sided consent" for teams only; one-to-one
chat still needs an accepted intro. Joining a team does **not** create a connection.

### Blocks

- A person cannot be invited to, join, ask to join, or be suggested for a team that has a
  member on either side of a block with them. They are told only that the team is not
  available, never who.
- **Blocking a teammate takes the two people out of the same team:** if the blocker is the
  owner, the blocked person is removed; otherwise the blocker leaves. Nobody is told why.
- Listed teams owned by someone on either side of a block with the viewer are not shown.

### Team chat

Delivered by polling, as ADR 0012 decided. The existing "what changed in my conversations"
poll also returns new team messages, so a client still makes **one** poll and the per-person
and global poll caps do not change. Team messages count against the same
`MESSAGES_PER_DAY`. A message is stored once however many members read it. Read state is
`team_members.read_at`.

### Limits (zero-cost rule 5)

| Limit | Value |
| --- | --- |
| People in a team | 6 |
| Teams a person can be in at once | 5 |
| Teams a person can own at once | 3 |
| Team invites sent per person per day | 10 |
| Requests to join per person per day | 5 |
| Pending invites and requests per team | 20 |
| Goals per team / skills per person per team | 30 / 10 (as pair spaces) |
| Goal, skill and note writes | Shared with `SPACE_WRITES_PER_DAY` (100) |
| Team messages | Shared with `MESSAGES_PER_DAY` (300) |

All team writes are storage-guarded (`require_storage_capacity`). A new `teams` feature
switch (admin Settings, A6) turns the whole feature off with `503 feature_off`. **It stays
off on staging and production until the reporting PR has merged.**

### Retention

| Data | Kept |
| --- | --- |
| Team messages | 90 days after sending (`MESSAGE_RETENTION_DAYS`) |
| Progress notes | 90 days after writing (`SPACE_RETENTION_DAYS`) |
| Invites and join requests | Pending ones expire after 14 days; answered or expired ones are deleted after 90 days |
| A closed team | Hidden from everyone at once; the team and everything in it deleted 90 days later |
| A person who leaves or is removed | Membership row deleted at once; their messages, goals and notes stay with the team under the rules above |
| Account deletion | Memberships, invites, messages and entries written by that person are deleted (ON DELETE CASCADE); an owned team passes to the longest-standing member first |

### Reporting and moderation

New report targets: **`team`** (its name, description and "looking for" text) and
**`team_message`** (frozen copy of the message and the 10 before it, as for chat). Team
goals and notes use the existing `goal` and `progress_log` targets. Moderators can remove a
listing or close a team; both are written to the audit log. Listed-team text also goes
through the content rules (A7), since strangers can read it. This PR, and the privacy and
terms wording that goes with it, **stops for the owner's review**.

### Notifications and email

In-app only: invited to a team, someone asked to join, someone joined, your request was
accepted. **No email in v1** (the non-login email budget is small).

### API

Plain REST under `/api/v1/teams`, designed for any client: teams, members, invites, join
by code, listed teams, goals, skills, notes and messages. Exact shapes come with each
backend PR and the OpenAPI spec.

### Web

A "Teams" item in the app shell beside "Pair spaces": my teams, create a team, a team page
(chat, goals and notes, members), browse listed teams, and the join-by-link page. Built
from `components/ds`.

## Build order

One PR at a time. Each migration PR is followed by Migrate staging.

| PR | What | Migration |
| --- | --- | --- |
| T1 | Teams, members, inviting a connection, leave, remove, close; `teams` switch; notifications | yes |
| T2 | Team goals, skills and progress notes (the pair-space tables take teams) | yes |
| T3 | Team chat in the existing poll | yes |
| T4 | Web: my teams, create, team page, invites | no |
| T5 | Invite links (API and web) | yes |
| T6 | Listed teams and asking to join (API and web) | yes |
| T7 | Matcher finds teammates (API and web) | yes |
| T8 | Reports for teams and team messages, moderator actions, privacy and terms wording. **Owner review, no auto-merge.** Only then is the switch turned on | yes |

## Consequences

**Positive**

- No new service; chat keeps one poll; the matcher is reused whole.
- Pair spaces and one-to-one chat are untouched for people who only want those.
- Retention is bounded for every new table.

**Negative / risks**

- **Storage.** Estimate, not a measurement: about 20 KB more per person (team messages
  about 60 kept per person × ~360 B, plus memberships, invites and team entries). That
  moves the 350 MB budget from about 2,400 people to about 2,100. `docs/storage-budget.md`
  gets its rows in the PRs that add the tables.
- **Weaker consent than one-to-one** (see above). Links can be passed on to anyone signed
  in until they expire or are reset.
- **More to moderate:** listed teams are the first user-written text that strangers can
  browse. The content rules and the report target are the controls.
- **Two concepts for users** ("Pair spaces" and "Teams") that do similar things.
- The pair-space tables become a little harder to read (two kinds of parent, two ways to
  name the author).
- T7 touches the matcher, which is being changed in other work; it is last among the
  feature PRs so it can build on that.

## Open questions for the owner

Defaults are in the text above; say if any should differ.

1. Blocking a teammate: the blocker leaves (or, if they own the team, the blocked person is
   removed). Is that right?
2. May any member invite, or only the owner (the default)?
3. Should a joiner by link get in at once (the default), or wait for the owner's yes?
4. Auto-merge for T1 to T7 once the five checks are green, with T8 stopping for review?
