# 22. Chip-first onboarding

- **Status:** Accepted
- **Date:** 2026-11-12
- **Relates to:** [ADR 0007](0007-ai-gateway.md), [ADR 0014](0014-design-system-cynergi.md),
  [ADR 0020](0020-skill-suggestions.md)
- **Design:** [docs/design/onboarding/](../design/onboarding/) (brief, mockups, build prompts)

## Context

Onboarding asks for a free-text "About you" paragraph (20 to 2,000 characters) before
anything else. Most people who sign in never finish it, so most accounts stay empty.
ARCHITECTURE.md's principle "Describe, don't fill forms" made free text the only way in. The
redesign (brief and mockups in `docs/design/onboarding/`) asks for taps first: what you are
here for, what you offer, what you want, a few details. The system then writes the "about"
text for you to check and edit.

## Decision

**Flow.** Five steps: (1) intents, (2) skills offered, (3) skills wanted, interests and an
optional 140-character note, (4) year, branch, availability and display name, (5) check what
was understood. Steps 2 to 4 have "Skip for now". Free text is optional everywhere. The
principle becomes "Tap first, describe if you like": the free-text path stays (the You page,
and step 5's editable about text), but it is no longer the way in.

**Storage: chips in their own columns, not in `structured`.** On `profiles`:

| Column | Type | Cap |
| --- | --- | --- |
| `offer_skills`, `want_skills`, `interest_tags` | `varchar(60)[]` | 20 each |
| `want_note` | `varchar(140)` | 140 |
| `study_year` | `varchar(8)`, CHECK `1`–`4`, `postgrad` | nullable |
| `branch` | `varchar(16)`, CHECK of eight values | nullable |
| `onboarding_saved`, `onboarding_skipped` | `varchar(8)[]`, CHECK of step names | 4 / 3 |
| `onboarding_completed_at` | `timestamptz` | null until finished |

Why columns: `structured` is derived. Every parse replaces it, so chips stored there would be
overwritten or need merging rules. The chips are what the person said, like
`raw_about_text`, and `structured` stays what the system derived from them (step 5 rebuilds
it from the chips and the about text, so embeddings and matching keep reading the same
shape). Columns also get CHECK caps like every other field, and an array can be counted with
an index for the aggregate counts the redesign shows. Tags stay plain strings (ADR 0020):
nothing records whether a chip came from the suggestion list. Intents, available days,
weekly hours and display name reuse the existing columns. The mockup's hours bands (1–2,
3–5, 6–10, 10+) are shown with the stored values (1–3, 4–6, 7–10, 10+) instead of adding new
ones.

**Saving, skipping and resuming.** `PUT /api/v1/me/onboarding/{intents|offers|wants|about}`
saves one step; `POST /api/v1/me/onboarding/{offers|wants|about}/skip` skips one (anything
already saved stays). A step is either saved or skipped, never both. `GET
/api/v1/me/onboarding` returns the picks, each step's state and `next_step`: the first step
neither saved nor skipped, `review` when only step 5 is left, or `null` once finished. The
first step save creates the profile row with no about text, so `parse_status` stays `empty`:
no AI reads anything, and matching (which needs a parsed, embedded profile) ignores the
person until they finish. Responses are data only; no UI copy.

**Finishing.** `onboarding_completed_at` is set when onboarding is finished. Until step 5
exists, the first full profile save (`PUT /me/profile`, with AI consent) finishes it.
Existing profiles were all made through the old onboarding, so the migration backfills the
column with `created_at`. Clients use `onboarding_completed_at` (or `next_step`), not "a
profile row exists", to decide whether to show onboarding.

**AI consent** (ADR 0007, section 5) is unchanged: it is still required before any AI reads
profile text, and the step saves above never send anything to an AI provider. Step 5 decides
where the unchanged consent line sits in the new flow (owner review).

**Later pieces, recorded here so the data stays in one place.**
- Dismissed nudges (screen 11): a small `varchar[]` of nudge kinds on `profiles`.
- Reminder emails (screen 12): two nullable `timestamptz` "sent" markers on `users` (a person
  who never saved step 1 has no profile row). No new growing table.
- Aggregate counts ("23 people are looking for Python skills this week"): counts only,
  hidden below a minimum (5 for demand, 10 for "joined this month").

**Home, strength and nudges (onboarding P4).**
- *Strength* is computed by the API only (`services/profile_strength.py`) and returned with
  the profile and the onboarding progress as `{percent, done, total, missing}`. `missing`
  holds stable item codes (`intents`, `offers`, `wants`, `about_text`, `availability`,
  `headline`, `links`); clients choose the words and the links.
- *Soft gate*: sending an intro, asking to join a team, joining by link and accepting a team
  invite need at least 3 offered skills (`409 skills_required`). Clients ask for them inline
  and retry. Migration 0037 fills empty chip columns from `structured` for older profiles,
  so nobody who already listed skills is stopped.
- *Nudges* (screen 11): `GET /me/nudge` hands out at most one a day; each kind is shown on
  one day at most and never again once dismissed (owner-approved default). Kinds:
  `team_skill` (a team just joined names a listed skill the person doesn't offer) and
  `availability` (after a first match, with no days set). Stored as `nudges_shown`,
  `nudges_dismissed` and `nudge_shown_at` on `profiles`.
- *Demand* (screen 8): `GET /stats/demand?skill=` returns a count of other active, unblocked
  people who wanted the skill in the last 7 days (a want chip saved, or a request asking for
  it), or `null` below 5. Never names or pictures.
- The You page's skill editors now write the chip columns (`PATCH /me/profile`), and the
  matcher's view follows them.

## Consequences

- Profiles can now exist without about text. Code that treats "has a profile" as "is
  onboarded" must use `onboarding_completed_at` instead (the web app moves over with the new
  screens).
- The You page's skill editors write the chip columns (onboarding P4); `structured` follows
  them, so the two no longer differ.
- Year and branch are new personal data: optional, never shown to others in this change,
  never sent to an AI provider, deleted with the account, and listed in the privacy policy.
- Matching does not read the new columns until step 5 builds `structured` from them.
