---
description: Build the onboarding redesign end to end (prompts 0–6), one PR at a time, resuming where it left off
---

Build the onboarding redesign by working through every prompt in
docs/design/onboarding/claude-code-prompts.md (Prompt 0 to Prompt 6), in order, one PR at a
time, without asking me to type anything between them. Follow CLAUDE.md throughout. Each
prompt's own standing rules still apply in full. This file only removes the manual hand-offs.

## 1. Find where we are (do this first, and again after any restart)

- PR titles for this work always start with `Onboarding P<N>:` (for example
  `Onboarding P2: steps 1–4`). Run
  `gh pr list --state all --search "Onboarding P in:title" --json number,title,state,headRefName`.
- A prompt is done when its PR is MERGED. If a PR is OPEN, pick that prompt up where it
  stands: CI running, CI failed, or waiting for my review. Otherwise start the lowest
  prompt number not yet done.
- Tell me in one line which prompt you're on and why, then carry on.

## 2. For each prompt

1. `git fetch origin && git switch main && git pull --ff-only`, then a new branch
   `feat/onboarding-p<N>-<short-name>` (docs-only P0: `docs/onboarding-p0-design-files`).
2. Do the prompt exactly as written.
3. Open the PR with the `Onboarding P<N>:` title prefix and the repo's PR template.
4. Wait for CI in the background: `gh pr checks <number> --watch`. If a required check
   fails, read the logs (`gh run view --log-failed`), make one fix and push. If it fails
   again, STOP and tell me (CLAUDE.md rule).
5. Then:
   - **Auto-merge prompts (0, 2, 4)**, when the prompt's conditions held: enable auto-merge
     with the merge method recent merged PRs use, and wait for the PR to merge.
   - **STOPS FOR REVIEW prompts (1, 3, 5, 6)**, or an auto-merge prompt whose conditions
     did not hold: do NOT enable auto-merge. Tell me the PR number and what to look at,
     then wait for me to merge it on GitHub. Wait with a background command, not by asking
     me to type, for example:
     `until [ "$(gh pr view <number> --json state -q .state)" != "OPEN" ]; do sleep 300; done`
     While waiting, if I leave review comments asking for changes, address them, push and
     wait again. If I close the PR without merging, STOP and ask me.
6. After it merges: if it added a migration, run the staging migration steps in CLAUDE.md
   (Actions → Migrate staging, check the revision and the Staging migrations check) and
   tell me the migration number. Never touch production.
7. Go straight on to the next prompt.

## 3. Hand-offs I am approving in advance

- Prompt 0's "wait for my go-ahead before prompt 1": put the report in the PR description
  and in the chat, then continue to prompt 1 without waiting. Stop only if the report
  finds a blocker: a conflict with an ADR or CLAUDE.md, or a choice only I can make that
  no later review PR will cover.
- If the report says prompts 1–6 should change, follow the adjusted plan and note it in
  each PR description.
- Prompt 4's "Say how often a nudge may show; I'll confirm": choose a conservative default
  (each nudge shown at most once, at most one nudge per day), state it in the PR
  description, and continue.
- Any other "tell me and wait" inside a prompt means: tell me, then keep going, unless it
  is a STOPS FOR REVIEW point or a failure.

## 4. Always stop and ask me when

- CI fails twice on the same PR.
- Something needs a secret, a paid service, production access, or a change outside the
  prompt's scope.
- Wording about privacy, consent, moderation, reporting, blocking, legal, terms or email
  preferences changes in a PR that wasn't already marked STOPS FOR REVIEW.

When Prompt 6 has merged, give me a short summary: each PR's number and title, the
migrations added, and anything left for later.
