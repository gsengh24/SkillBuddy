# Claude Code prompts: onboarding redesign

How to use: type `/build-onboarding` in Claude Code once. It runs every prompt below in order, one PR at a time, and goes on to the next prompt by itself. It pauses only at prompts marked STOPS FOR REVIEW: you review and merge those PRs on GitHub, and it notices the merge and carries on. If the session ends or restarts, type `/build-onboarding` again; it works out from the PR titles (`Onboarding P<N>: …`) where it left off. The command lives in `.claude/commands/build-onboarding.md`.

To run one prompt by hand instead, paste its whole block into Claude Code. Each block has the standing rules in it.

Source material, all in this folder once prompt 0 has merged:
- `ONBOARDING-DESIGN-BRIEF.md`: the brief, covering flow, screens, copy, content rules and limits.
- `01-…12-….html` and `index.html`: the mockups at 390px and 1280px. Open them in a browser. Edit them in `src/`, then rebuild with `python3 docs/design/onboarding/src/build.py`.
- Where a mockup and the brief disagree on looks, the mockup wins. One deliberate case: screen 3 doesn't reuse step 2's chip layout. Want chips are ink, offer chips are green, suggestions that pair with your offers come first, and a "You offer ⇄ You want" summary sits beside the picks.

Order:
0. Add the brief and mockups, then a read-only gap report and PR plan
1. Profile data for the new flow: backend, migration, API (STOPS FOR REVIEW)
2. Onboarding steps 1–4
3. Step 5: check what we understood (STOPS FOR REVIEW)
4. Home with an unfinished profile, soft gate, You page strength meter, nudges
5. Resume import and paste anything (STOPS FOR REVIEW)
6. Re-engagement emails (STOPS FOR REVIEW)

---

## Prompt 0: add the design files, then a read-only report

```
Standing rules (apply to this whole task):
- Work on a short-lived branch cut from an up-to-date main, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow unless this prompt says so.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Task: add the onboarding design files to the repo, then report. Docs only, no app code changes.

1. Move ONBOARDING-DESIGN-BRIEF.md from the repo root into docs/design/onboarding/. Commit the whole docs/design/onboarding/ folder (brief, 12 mockup HTML files, index.html, src/, this prompts file) and .claude/commands/build-onboarding.md. Leave MATCHMAKING-NOTES.md alone.
2. Read the brief fully, then open every mockup. Read CLAUDE.md, docs/ARCHITECTURE.md, docs/design/design-spec.md, ADR 0007, 0014, 0017, 0020 and 0021. Mockups win over the brief on looks (screen 3 differs from the brief on purpose: see the top of docs/design/onboarding/claude-code-prompts.md).
3. This PR changes no app wording, so auto-merge is allowed once the five checks are green.
4. Then report in the chat, with no code changes:
   a. How onboarding works today: /onboarding, ProfileForm, profile creation, parsing (parse_status, structured), the AI consent step (ai_consent_at / ai_consent_version), and where people land after it.
   b. For each of the 12 screens: what already exists (components in components/ds, endpoints, jobs, fields), what is missing, and what is new.
   c. Data gaps. Which fields the new flow needs that the profile model doesn't have (for example year, branch, chip-picked offers, wants and interests, the optional "anything specific" line, onboarding progress for skipped steps), and how you'd store each one. Say whether chip picks should live in `structured` or in their own columns, and why.
   d. How the step 5 "about" text should be made: the AI gateway in a job, with a template fallback that needs no model. Also how the loading and fallback states get their status.
   e. Resume import and paste: how to read a PDF in the browser with nothing uploaded, which library (licence, bundle size, CSP: worker-src and wasm), how personal details are stripped before anything leaves the browser, and whether skill suggestions can come from the bundled list in ADR 0020.
   f. Re-engagement emails: which email preference they respect, how the day 3 and day 10 sends are scheduled through the existing tick, and how they stop.
   g. Aggregate social proof ("23 people are looking for Python skills this week"): where the count comes from, and a minimum count below which it is hidden.
   h. Anything in the brief or mockups that conflicts with the ADRs or CLAUDE.md, and your proposed fix.
   i. Which ADR(s) this needs, and the final PR plan. Adjust prompts 1–6 if the plan should differ, and say how.
5. Tell me the PR number, then wait for my go-ahead before prompt 1.
```

---

## Prompt 1: profile data for the new flow (STOPS FOR REVIEW)

```
Standing rules (apply to this whole task):
- Work on a short-lived branch cut from an up-to-date main, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- Do not touch production. Never run migrations against production.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- In the PR description, include a short summary, how it was verified, anything not verified, and any decision I need to make.

Read docs/design/onboarding/ONBOARDING-DESIGN-BRIEF.md and your prompt 0 report (section c). Prompt 0 must be merged first.

Task: PR 1. Backend only: the data and API the new onboarding flow needs. No frontend screens yet.

1. Write the ADR for the onboarding redesign: the chip-first flow, what is stored and where, skipping and resuming, and why. Link it from ARCHITECTURE.md.
2. Add the fields from the report with an Alembic migration (CHECK constraints, not enums; downgrade must work). Cap every text field (the "anything specific" line is 140). Nothing added here is a growing table; if one is, state its retention and add a row to docs/storage-budget.md.
3. Endpoints under /api/v1 to save each step on its own (partial saves, so "Skip for now" works) and to read onboarding progress. These stay frontend-agnostic: no UI copy in responses. Use the error envelope, require auth, keep CSRF, and add Depends(require_storage_capacity) on writes.
4. Keep the existing free-text profile path working until prompt 3 replaces it.
5. Integration tests for each endpoint: success, validation, unauthorised, and not found where it applies. Regenerate docs/api/openapi.json.
6. THIS PR STOPS FOR MY REVIEW (data model change). Do NOT enable auto-merge. When the five checks are green, tell me the PR number and wait. After I merge it, run Actions → Migrate staging (gh workflow run "Migrate staging" --ref main), wait for it, confirm "Revision after upgrade" shows the new head and the Staging migrations check is green, and tell me the migration number.
```

---

## Prompt 2: onboarding steps 1–4

```
Standing rules (apply to this whole task):
- Work on a short-lived branch cut from an up-to-date main, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read the brief and open mockups 01–04 in docs/design/onboarding/. Prompt 1 must be merged first.

Task: PR 2. Build onboarding steps 1–4 at /onboarding, using the prompt 1 endpoints.

1. Screen 1 What brings you here (intent cards; Continue is disabled until one is picked; no Skip). Screen 2 What you're good at (search, grouped chips, the "Skip the typing" panel; its two buttons can be disabled placeholders until prompt 5). Screen 3 What you're looking for (follow mockup 03, not the brief's "same chip layout": ink want chips with +/✓, the "Pairs well with what you offer" group first, Browse all skills folded, and the You offer ⇄ You want summary beside the picks on desktop and under the headline on phone). Screen 4 A bit about you.
2. Build from components/ds and design tokens only; add any missing component (selectable chip with an ink variant, intent card, step progress bar, segmented control) to components/ds with tests. Don't copy the mockup CSS class names; they are a visual reference. Fonts are self-hosted as today, not Google Fonts.
3. Progress bar and "Step n of 4" at the top. Steps 2–4 have "Skip for now". Each step saves as it goes, so leaving and returning resumes at the right step. The footer is sticky on phone.
4. 44px touch targets on phone. Visible focus ring. Chips are buttons with aria-pressed, the year control is a radiogroup, and the counts are announced politely. Motion only as in design-spec section 5, off with prefers-reduced-motion.
5. Skill search uses GET /api/v1/skills/suggest (ADR 0020): suggest, don't force.
6. Keep the existing AI consent step and its wording exactly as they are, and say where it now sits in the flow. If its wording or placement has to change, STOP FOR MY REVIEW instead of auto-merging.
7. Component tests for each step, plus a Playwright happy path (pick, skip, resume).
8. Screenshots of each step at 390px and 1280px next to the matching mockup.
9. Auto-merge is allowed once the five checks are green, if point 6 held.
```

---

## Prompt 3: step 5, check what we understood (STOPS FOR REVIEW)

```
Standing rules (apply to this whole task):
- Work on a short-lived branch cut from an up-to-date main, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- Do not touch production. Do not run any migration workflow unless this prompt says so.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read the brief and open mockup 05. Prompt 2 must be merged first. Backend changes and an OpenAPI update are allowed in this PR.

Task: PR 3. Step 5: write the "about" text from the chips and show the anonymous match card preview.

1. A job builds the about text through the AI gateway only (CLAUDE.md rule 4), with Pydantic-validated output, one retry, and redacted alias-only input. The fallback is a template made from the chips alone ("Offers: React, Figma. Wants: a backend partner. Into: chess, hackathons."), used when the AI is off, over its cap or failing. Matching must still work end to end on the fallback.
2. The API returns immediately. The page shows the loading skeleton ("Reading your profile…"), then the ready card or the fallback with the muted note "We'll polish this shortly." Never show an error state.
3. The preview card follows the content rules: no name, photo or contact details; heading, one sentence, topic chips, intents, availability.
4. The about textarea is editable, with a 500 cap and counter. "Looks good" finishes onboarding and goes to Home; "Edit" goes back to the steps.
5. Retire the old free-text-first onboarding path, or say why it should stay.
6. Tests: job success, invalid model output, fallback, and the endpoint paths. Frontend tests for all three states. Screenshots of all three states at 390px and 1280px.
7. THIS PR STOPS FOR MY REVIEW (AI-facing wording and what is shown to other people). Do NOT enable auto-merge. When the five checks are green, tell me the PR number and wait. If it added a migration, follow the staging migration steps in CLAUDE.md after I merge.
```

---

## Prompt 4: Home with an unfinished profile, soft gate, strength meter, nudges

```
Standing rules (apply to this whole task):
- Work on a short-lived branch cut from an up-to-date main, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- Do not touch production. Do not run any migration workflow unless this prompt says so.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read the brief and open mockups 08, 09, 10 and 11. Prompt 3 must be merged first. Backend changes and an OpenAPI update are allowed in this PR.

Task: PR 4. What people see when their profile isn't finished.

1. Screen 8: on Home, an unfinished profile replaces the empty inbox with the "Finish your profile" panel (meter, steps left, "Finish in 60 seconds"). The composer still works, and "Find matches" is an outline button so there's only one primary. The aggregate social proof line uses an endpoint that returns a count only, hidden below the minimum from your prompt 0 report. Never return names or avatars.
2. Screen 9: the soft gate dialog, shown when someone with fewer than 3 skills tries to send an intro or join a team. Inline chip picker, "1 / 3" counter, "Save and continue" disabled until 3, "Not now". Focus is trapped and returns on close; Escape closes it. The server enforces the same rule, not just the UI.
3. Screen 10: the profile strength meter on the You page header card, with missing items as links, and "See how others see you". Strength is computed in one place (backend), not duplicated in the frontend.
4. Screen 11: in-context nudges ("You joined the ML space. Add Machine learning to your skills?" and the availability one). One at a time, dismissible, and a dismissed nudge doesn't come back. Say how often a nudge may show; I'll confirm.
5. Tests for each, and screenshots at 390px and 1280px next to the mockups.
6. Auto-merge is allowed once the five checks are green, as long as no privacy, consent or legal wording changed. If it added a migration, follow the staging migration steps in CLAUDE.md after merge.
```

---

## Prompt 5: resume import and paste anything (STOPS FOR REVIEW)

```
Standing rules (apply to this whole task):
- Work on a short-lived branch cut from an up-to-date main, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read the brief and open mockups 06 and 07. Prompt 2 must be merged first.

Task: PR 5. The "Skip the typing" shortcuts on step 2.

1. Write an ADR for in-browser PDF reading: the library, its licence (free and open source, no card), bundle size, lazy-loaded only on this screen, and the CSP change it needs. Keep the CSP otherwise as strict as today.
2. Screen 6: pick a PDF up to 2 MB, read it in the browser only, show the reading steps, then the suggestions. The file is never uploaded or stored (Storage rule 1 in CLAUDE.md).
3. Screen 7: paste text up to 2,000 characters, then the suggestions.
4. Strip personal details (emails, phone numbers, links, names in the header) in the browser before anything is sent. Prefer suggestions from the bundled skill list (ADR 0020). If any text must go to the server, send only the redacted text, never store it, and say so in the PR.
5. The person confirms every chip; nothing is saved until they do. Confirmed chips go back into step 2.
6. Tests, including a fixture PDF made from synthetic data only, and screenshots of every state at 390px and 1280px.
7. THIS PR STOPS FOR MY REVIEW (privacy wording: "Read in your browser, never uploaded or stored."). Do NOT enable auto-merge. When the five checks are green, tell me the PR number and wait.
```

---

## Prompt 6: re-engagement emails (STOPS FOR REVIEW)

```
Standing rules (apply to this whole task):
- Work on a short-lived branch cut from an up-to-date main, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- Do not touch production. Do not run any migration workflow unless this prompt says so.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read the brief and open mockup 12. Prompts 1–4 must be merged first. Backend changes are allowed in this PR.

Task: PR 6. Two reminder emails for people who signed up but didn't finish their profile.

1. Day 3 and day 10 (the last one says "We'll stop reminding you after this."). Never more than these two per person, and none once the profile is finished.
2. Sent only from a worker job through EmailSender, scheduled through the existing admin tick (no new cron). Respect the person's email preference. Never log full addresses (mask_email).
3. The aggregate count in the subject and body uses the same endpoint and minimum as prompt 4. If the count is below the minimum, use the wording without a number.
4. Plain HTML, 600px wide, inline styles, no images (the wordmark is text), one button "Finish my profile", and the footer about turning alerts off in You → Alerts.
5. Record what was sent so jobs are idempotent (the runner retries). State its retention and add a row to docs/storage-budget.md if it's a growing table.
6. Tests: who gets which email, nobody gets it twice, the preference is respected, and finished profiles are skipped. Attach the Mailpit renders of both emails.
7. THIS PR STOPS FOR MY REVIEW (email and consent wording). Do NOT enable auto-merge. When the five checks are green, tell me the PR number and wait. If it added a migration, follow the staging migration steps in CLAUDE.md after I merge.
```
