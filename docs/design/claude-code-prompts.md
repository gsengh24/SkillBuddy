# Claude Code prompts for the Cynergi redesign

How to use: do the prompts in order, one PR at a time. Paste one whole prompt block into Claude Code. Each block already contains the standing rules, so nothing else is needed. Wait for the PR to finish before starting the next one. Prompts marked STOPS FOR REVIEW will not auto-merge, you review and merge them yourself.

Before prompt 0: put these four files in a folder on your laptop, e.g. `C:\design-drop\`: `design-spec.md`, `reference-landing.html`, `reference-home.html`, and your logo file. Rename the logo to `cynergi-logo-source.jpeg` first (no spaces). Prompt 0 tells Claude Code to read them from there.

Order:
0. Add design files and report on the current frontend (read-only report, small docs PR)
1. Foundations: tokens, fonts, brand constant, base components
2. App shell, loading states, parallel calls
3. Home: requests and messages on one page
4. Matches, intro form and chat restyle (STOPS FOR REVIEW)
4B. Home layout v2: composer view on the right, calmer left pane, phone composer (run after prompt 4 is merged)
5. Pair spaces restyle
6. Profile and Settings restyle (STOPS FOR REVIEW)
7. Landing page
8. Privacy and terms restyle plus rename wording (STOPS FOR REVIEW)
9. Moderation pages restyle
10. Remaining rename text: titles, metadata, emails, docs (STOPS FOR REVIEW)

---

## Prompt 0: design files and read-only report

```
Standing rules (apply to this whole task):
- Work on a short-lived branch, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Task: add the design files to the repo and report on the current frontend. Docs only, no app code changes.

1. Copy these from C:\design-drop\ into docs/design/: design-spec.md, reference-landing.html, reference-home.html, and cynergi-logo-source.jpeg. If a file is missing, tell me which one and stop.
2. Read design-spec.md fully. It is the contract for the redesign. The two reference HTML files are the visual source of truth: where they disagree with the spec on looks, the HTML wins.
3. Do NOT change any app code, test, check, secret or migration. This PR touches no legal wording, so auto-merge is allowed once the five checks are green.
4. Then report, in the chat, with no code changes:
   a. Every frontend route and page (public, app, moderation), its main components, and which are legal-sensitive.
   b. The styling approach (Tailwind, CSS modules, other), existing design tokens, component library, and how fonts load now.
   c. What the CSP in next.config allows. Would it block self-hosted next/font fonts, inline SVG, own-domain images, or CSS animations? What exactly does the Smoke CSP check test?
   d. Every place "Skill Buddy" or "SkillBuddy" appears: UI text, titles, metadata, emails, backend, docs, cookie and storage keys, OpenAPI title, legal text.
   e. Current first-load JS size per route.
   f. Whether the earlier loading.tsx plus Promise.all speed work is merged. If not, say what is missing.
   g. Which endpoints the current Messages page and Discover page call, and which emails or notifications link to /messages.
   h. Anything in the spec that conflicts with how the app works today, and your proposed fix.
5. Tell me the PR number, then wait for my go-ahead before prompt 1.
```

---

## Prompt 1: foundations

```
Standing rules (apply to this whole task):
- Work on a short-lived branch, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read docs/design/design-spec.md and open docs/design/reference-landing.html and docs/design/reference-home.html. They are the contract for this work.

Task: PR 1 of the Cynergi redesign. Foundations only. No page redesign yet, so existing pages should keep working and just pick up the new base styles.

0. Design rules: add ADR 0014 (replaces ADR 0010) and update the design rules in CLAUDE.md for the new look: the new palette, solid ink primary buttons, green or ink avatars chosen by a stable hash of the person's id, and motion allowed only as in spec section 5 (transform and opacity, off for reduced motion). Update the token and contrast tests to the new values. The contrast tests must still enforce the same minimum ratios, only on the new colours, and no test may be weakened. List every test you changed and why.
1. Design tokens: add every token in spec section 2 as CSS variables on :root, and mirror them in the Tailwind or CSS configuration the repo uses. Components use tokens only, no raw hex.
2. Fonts: self-host Inter Tight (display), Inter (body) and JetBrains Mono (labels) with next/font, Latin subset only, display: swap. If Inter Tight is not available through next/font, use Geist and tell me. No Google Fonts requests at runtime. Confirm the CSP is unchanged and Smoke shows no violation.
3. Brand: create one brand constant (name "cynergi", display name "Cynergi", tagline, source of the contact address which must stay in frontend/lib/legal.ts) and one Logo component that renders the placeholder four-dot mark plus the lowercase wordmark. The real logo file is in docs/design/. Do not use it yet: it is teal and lavender on plum and does not match the palette. Tell me its pixel size and whether it is vector or raster.
4. Base components from spec section 4 (items 1 to 20): Button (primary, outline, ghost), Panel, Chip, TopicChip, Badge, SegmentedControl, ListRow, Avatar, Input and Textarea, Accordion, Skeleton, NumberedRow, CtaBand, Footer, PixelPattern, BottomNav, TopBar, Toast and inline error. Do NOT build the keycap chip or any single-key shortcut (not in v1).
5. Motion: add one useInView hook and the shared fade-up, plus the prefers-reduced-motion rule. Only transform and opacity.
6. A dev-only route /design that shows every component in its states at phone and desktop widths, for my review. It is enabled only when an env flag read through lib/env.ts is on, the flag is on for Vercel preview deployments only and off in production, and the page is excluded from the sitemap and set to noindex. Add a test that /design answers 404 when the flag is off.
7. Add tests: components render, buttons are keyboard operable, accordion toggles with aria-expanded, reduced motion removes animation classes.
8. Do not touch legal-sensitive screens, backend, migrations or docs/api/openapi.json. Report first-load JS per route before and after.
9. Auto-merge is allowed once the five checks are green, because this PR changes no legal wording. Then tell me the PR number and exactly how to open /design from the Vercel preview link on the PR (it will not exist on the production deployment).
```

---

## Prompt 2: shell, loading states, parallel calls

```
Standing rules (apply to this whole task):
- Work on a short-lived branch, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read docs/design/design-spec.md and the two reference HTML files. Prompt 1 (foundations) must be merged first, check that it is.

Task: PR 2. App shell, loading states and parallel data fetching.

1. App shell: phone gets the BottomNav (Home, Spaces, Saved, You, active item in green, safe-area padding). Desktop gets the TopBar with the same four links plus the bell. Keep every existing route reachable. The old "Messages" nav item goes away, it is merged into Home in PR 3. Do not delete the /messages route yet.
2. Add loading.tsx skeletons for every route group, styled with the Skeleton component, so a click responds immediately.
3. On each page, run independent API calls in parallel with Promise.all. Keep /auth/me first only where the page truly needs its result before anything else, otherwise run it together with the data calls (the API already checks the session on every call). Pages: Messages, a chat (the last three calls together), Pair spaces, a pair space, Profile, Settings.
4. No backend change, no new endpoint, no migration, docs/api/openapi.json must not change.
5. Do not restyle legal-sensitive screens in this PR. The shell is allowed to wrap them. Update only the expected nav text in login.spec if the tab names change.
6. Measure before and after: time from click to first content on staging-like conditions, and first-load JS per route. Report both.
7. Tests for the shell navigation (keyboard, aria-current) and for the skeletons.
8. Auto-merge allowed once the five checks are green. Tell me the PR number and the before and after numbers.
```

---

## Prompt 3: Home, requests and messages on one page

```
Standing rules (apply to this whole task):
- Work on a short-lived branch, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read docs/design/design-spec.md section 6.2 and open docs/design/reference-home.html in a browser at 390px and 1280px wide. Match it exactly. Prompt 2 must be merged first.

Task: PR 3. Merge requests and messages into one Home page.

1. Build /home as in spec 6.2. Phone: single column with the composer, the All / Requests / Messages segmented filter, and one list ordered by newest activity. Desktop (1024px and up): two columns, list on the left (400px), detail on the right.
2. List rows: request row (REQUEST badge, "n matches ready to view"), intro-received row (INTRO badge, what they asked for), message row (initials avatar, name only once connected as today, the status line described below, unread dot with an accessible label). Use only existing endpoints: /auth/me, /me/profile, /requests, /intros?box=received, /connections, /messages/updates, /notifications/unread-count. Fetch them in parallel. Do not add an endpoint or a backend field. There is NO message text preview in v1: a message row shows "n new messages" when unread_messages is above 0, otherwise "Open chat", and the time from last_message_at. If the existing endpoints cannot give "newest activity first" for the merged list, sort in the frontend and tell me.
3. Opening an item sets ?item=<type>-<id>. On desktop it fills the right pane. On phone it opens full screen with a back arrow. Back and refresh must work. The right pane shows the matches for a request, the intro (accept, decline, block, report), or the chat. Reuse the existing components for the chat, intro and match screens as they are for now, only wrapped in the new layout. Their restyle is PR 4.
4. Keep /messages/[id] as the chat page (deep links and report flows use it). Make /messages (the list) redirect to /home. Check every email template, notification and link that points to /messages and tell me which ones you changed. Update only the expected text in security.spec, social.spec, login.spec and discover.spec for the new headings and tabs, nothing else, and list each change.
4b. The greeting label must be set in the browser after load (first paint says "Hello"), never from the server clock.
5. Keep "Open pair space" on connected rows and the chat header. Keep block and report reachable exactly where they are today. Do not change their wording or behaviour.
6. Empty state ("Start your first request", one line, "Find people") and error state (one sentence, "Try again").
7. Tests: filter works and is keyboard accessible, deep link with ?item opens the right thing, /messages redirects to /home and /messages/[id] still works, unread dot has an accessible label, no endpoint other than the listed ones is called.
8. Screenshots at 390px and 1280px in the PR description next to the reference. Report first-load JS for /home before and after.
9. This PR wraps legal-sensitive screens but must not change their wording or behaviour. If you find you need to change any of them, stop and tell me. Otherwise auto-merge is allowed once the five checks are green. Tell me the PR number.
```

---

## Prompt 4: matches, intro form and chat restyle (STOPS FOR REVIEW)

```
Standing rules (apply to this whole task):
- Work on a short-lived branch, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read docs/design/design-spec.md and the reference HTML files. Prompt 3 must be merged first.

Task: PR 4. Restyle the match cards, the intro form, received intros and the chat with the new components.

1. Match card: topic chip, "Why this match" panel as in the hero grid, "Send an intro" with the optional note field (500 characters, counter in mono), Send intro (primary) and Cancel (ghost), the Report link and "Close this request". Keep every word of the privacy and consent text exactly as it is today.
2. Received intro: what they asked for, why they were matched, their note, Accept, Decline, Block, Report. Same wording and behaviour as today.
3. Chat: header with avatar, name, "Open pair space", menu with Block and Report. Message bubbles (in: panel, out: ink). The "Staying safe" tips at the start of a chat until it has 10 messages, exactly as built in PR #59. The report and block flows keep their wording and steps.
4. Do not change behaviour, copy, API calls, limits or data. Visual restyle only. List every legal-sensitive string you touched, or confirm none changed, in the PR description.
5. Tests: existing tests still pass unchanged, plus keyboard and screen-reader checks on the new controls.
6. Screenshots at 390px and 1280px, before and after.
7. THIS PR STOPS FOR MY REVIEW. It touches the report, block and consent screens. Do NOT enable auto-merge. When the five checks are green, tell me the PR number and wait.
```

---

## Prompt 4B: Home layout v2 (run only after prompt 4 is merged)

```
Standing rules (apply to this whole task):
- Work on a short-lived branch, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read docs/design/design-spec.md section 6.2 (version 2) and open docs/design/reference-home.html in a browser at 390px and 1280px wide. Match it exactly. Re-copy the latest design-spec.md and reference-home.html into docs/design/ first if they differ (small commit at the start of this PR). Prompts 3 and 4 must be merged first.

Task: PR 4B. Rework the Home layout. Layout and styling only.

Problems to fix: the right pane is a big empty space until something is opened, the left column is overloaded, "Home" appears twice, and the display headlines have letters touching.

1. Desktop (1024px and up): left pane 360px with the "Inbox" heading, a "New request" ghost button, the segmented filter and the list, nothing else. Right pane default state is the centred 640px composer view: greeting label (browser-side, first paint says "Hello"), two-tone headline "What are you building today?" / "Say it in a sentence." (the second line on its own line, muted), the composer on green tint with the textarea, the existing intent picker and the "Find matches" button, and under it the summary strip and the pair-spaces band side by side. When an item is opened it fills the right pane. "New request" and Escape return to the composer view. The selected row has the green tint.
2. Phone: no "Home" title in the top bar. Greeting, two-tone headline, then a COLLAPSED composer card (textarea and "Find matches" only). The intent chips and the counter appear when the textarea gets focus. Then "Inbox", the filter, the list, and the pair-spaces band last. No summary strip on phone.
3. Remove the suggestion pills ("a design partner", "learn React", and so on). Keep an sr-only h1 "Home" for screen readers.
4. Intent picker: keep every option, its behaviour, the 1000-character limit and the counter exactly as they are today. Restyle only: one green dot on every chip, selected chip filled green with a mint dot.
5. Headline tracking: set display type to -0.03em up to 52px and -0.04em from 56px up, as in spec section 3, through a single token. Apply it to every display headline already built (Home, hero, section headings), not only this page. Letters must not touch at any width.
6. Rows: title on one line with an ellipsis, times in mono that never wrap, REQUEST and INTRO badges as in the reference. Hide the pair-spaces band when the user has no connections.
7. No new endpoint, no backend change, no copy change in any legal-sensitive screen. The chat, intro, match, block and report screens are only wrapped, not edited. If you must touch one, stop and tell me. Update only the Home tests and, if the visible text changed, the expected text in the Smoke specs that check Home. List every test change.
8. Tests: composer view shows by default on desktop, opening an item replaces it, "New request" and Escape return, phone composer is collapsed until focus, filter works by keyboard, no endpoint other than the listed ones is called, headlines have the new tracking token.
9. Screenshots at 390px and 1280px beside the reference: desktop default, desktop with a chat open, phone default, phone with the composer focused. Report first-load JS for /home before and after.
10. Auto-merge is allowed once the five checks are green, as long as no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. If any did, stop for my review. Tell me the PR number.
```

---

## Prompt 5: pair spaces restyle

```
Standing rules (apply to this whole task):
- Work on a short-lived branch, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read docs/design/design-spec.md and the reference HTML files. Prompt 4 must be merged first.

Task: PR 5. Restyle /spaces and /spaces/[id] with the new components.

1. Spaces list: one row per connection with avatar, name, goal count, "Open space". Empty state with a verb button.
2. A space: shared goals, each person's skills, progress notes. Use Panel, ListRow, Chip, Button, Input. Keep the limits (30 goals, 10 skills each, 100 writes a day), the "Notes are deleted 90 days after they're written" line, and the report entries for goals and notes exactly as they are.
3. Visual restyle only. No behaviour, copy, API or data changes. If any report or privacy wording is touched, stop and tell me.
4. Tests unchanged and passing, plus keyboard checks.
5. Screenshots at 390px and 1280px.
6. Auto-merge allowed once the five checks are green, as long as no report, privacy, retention or terms wording changed. If any did, stop for my review. Tell me the PR number.
```

---

## Prompt 6: profile and settings restyle (STOPS FOR REVIEW)

```
Standing rules (apply to this whole task):
- Work on a short-lived branch, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read docs/design/design-spec.md and the reference HTML files. Prompt 5 must be merged first.

Task: PR 6. Restyle Profile, Settings (account, emails, blocked people), Saved and You.

1. Use Panel, Input, Button, SegmentedControl and ListRow. Keep every label, switch and helper text exactly as it is, including the "Emails about intros" switch and its wording ("We email you when someone sends you an intro or accepts yours.") and the Blocked people screen with Unblock.
2. No keyboard-shortcut setting in v1. Do not add one.
3. No behaviour, copy, API or data changes. List any legal-sensitive string you touched, or confirm none.
4. Tests unchanged and passing, plus keyboard and screen-reader checks.
5. Screenshots at 390px and 1280px.
6. THIS PR STOPS FOR MY REVIEW. It touches consent, email and blocking screens. Do NOT enable auto-merge. When the five checks are green, tell me the PR number and wait.
```

---

## Prompt 7: landing page

```
Standing rules (apply to this whole task):
- Work on a short-lived branch, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read docs/design/design-spec.md section 6.1 and open docs/design/reference-landing.html at 390px and 1280px wide. Match it exactly. Prompt 6 must be merged first.

Task: PR 7. Build the public landing page.

1. Sections in the order of spec 6.1: top bar, hero with the hero grid, How it works with the three numbered rows, three cards, FAQ accordion, CTA band, footer. Fade-up on scroll once, hero cells in sequence, button lift on desktop hover, all off for reduced motion.
2. Use real product pieces in the hero grid, no photos of people, no LocalCan material of any kind: no customer logos, quotes, testimonials, pricing, receipts or map.
3. Card copy and FAQ answers must match /privacy and the "no AI in chats" promise exactly. Use "Block or report from any chat" (never "one tap"). The legal row is "© 2026 Cynergi" with no "All rights reserved". Where the reference HTML has placeholder FAQ answers, draft the answers from docs/ and the live privacy page and mark each one in the PR description as "needs owner approval". Do not invent claims.
4. Footer links: Privacy, Terms, Contact (the address from frontend/lib/legal.ts).
5. The primary button goes to sign in or the existing entry point. No new backend work.
6. SEO basics: title, description, Open Graph with a generated static image using only our own assets, canonical, robots as they are today. No analytics, no third-party scripts.
7. Performance: keep first-load JS small, no large images, SVG and CSS for art. Report Lighthouse performance and first-load JS for / on mobile and desktop.
8. Tests: render, links, accordion, reduced motion.
9. Screenshots at 390px and 1280px beside the reference.
10. The FAQ answers about privacy are legal-sensitive. THIS PR STOPS FOR MY REVIEW. Do NOT enable auto-merge. When the five checks are green, tell me the PR number and wait.
```

---

## Prompt 8: privacy and terms restyle plus rename wording (STOPS FOR REVIEW)

```
Standing rules (apply to this whole task):
- Work on a short-lived branch, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read docs/design/design-spec.md section 10 and the reference HTML files. Prompt 7 must be merged first.

Task: PR 8. Restyle the privacy and terms pages and update the product name in them.

1. Restyle /privacy and /terms with the new type scale, hairline dividers and a sticky table of contents on desktop. Keep the /privacy#ai anchor working.
2. Replace "Skill Buddy" and "SkillBuddy" with "Cynergi" in both pages and in frontend/lib/legal.ts. Change no other wording. Both pages stay marked "Draft".
3. Set a new TERMS_VERSION that includes today's date and "-draft", and say which Render setting the owner must check.
4. Do not change retention periods, consent text, the contact address placeholder or anything else in the legal text. In the PR description, list every changed string as old text, new text.
5. Tests unchanged and passing, plus a test that no legal page still contains the old name.
6. Screenshots at 390px and 1280px.
7. THIS PR STOPS FOR MY REVIEW. Do NOT enable auto-merge. When the five checks are green, tell me the PR number and wait.
```

---

## Prompt 9: moderation pages restyle

```
Standing rules (apply to this whole task):
- Work on a short-lived branch, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read docs/design/design-spec.md and the reference HTML files. Prompt 8 must be merged first.

Task: PR 9. Restyle the moderation pages: report queue, resolve and suspend flows, resolved view, suspended accounts, and AI status with the "Test the AI providers" button.

1. Use the new components. Dense rows with hairlines, not cards. Functional first.
2. Keep every behaviour: moderator-only access with "not found" for others, the rate limit, the audit log, no secrets or user data in the AI status output (the existing test must keep passing), the limit of 5 provider test runs a day.
3. Visual restyle only. No wording, API or data changes. If any report or moderation wording must change, stop and tell me.
4. Tests unchanged and passing.
5. Screenshots at 390px and 1280px.
6. Because this PR touches moderation screens, THIS PR STOPS FOR MY REVIEW. Do NOT enable auto-merge. When the five checks are green, tell me the PR number and wait.
```

---

## Prompt 10: remaining rename text (STOPS FOR REVIEW)

```
Standing rules (apply to this whole task):
- Work on a short-lived branch, one PR for this task, never push to main.
- The task is done only when all five required checks are green: Backend, Frontend, Docker images, Smoke, Secret scan. Never weaken, skip or delete a test or check. If one fix attempt fails, stop and tell me.
- No secrets anywhere: not in the repo, scripts, notes, PR text or this chat. Do not ask me to paste a key.
- No backend change, no migration, no change to docs/api/openapi.json unless this prompt says so.
- Do not touch production. Do not run any migration workflow.
- Work only on what this prompt lists. If something else needs changing, tell me instead of doing it.
- Auto-merge is allowed after the five checks are green ONLY if this prompt says so and no privacy, consent, moderation, reporting, blocking, legal or terms wording changed. Otherwise stop for my review.
- In the PR description, include a short summary, the screenshots asked for, and any decision I need to make.

Read docs/design/design-spec.md section 10. Prompts 1 to 9 must be merged first.

Task: PR 10. Finish the user-facing rename from Skill Buddy to Cynergi.

1. Search the whole repo for "Skill Buddy", "SkillBuddy", "skillbuddy" and "skill-buddy". For each hit, decide: user-facing (change), identifier or URL (keep, list it), history (keep, ADRs get a one-line rename note).
2. Change: page titles, metadata, manifest, favicon and app icons (use the placeholder mark, one component or one SVG file), README, docs. Email names and subjects come from the backend app_name setting: do NOT change the backend default or the OpenAPI title in this PR. Tell me I should set APP_NAME=Cynergi in Render (no repo change), and list what a later small backend PR would change (default name, OpenAPI title, regenerated docs/api/openapi.json).
3. Do NOT rename the repository, the Render service, the Vercel project, environment variable names, cookie or storage keys, or database names. List any cookie or storage key that contains the old name and tell me what renaming it would do. Do not rename it.
4. Any email template or backend text that tells users about privacy, consent or moderation is legal-sensitive. List each one as old text, new text.
5. Add a short docs/rename.md with: what changed, what was kept and why, and the dashboard steps I must do myself (set APP_NAME=Cynergi in Render, Google OAuth consent screen name and logo before setting the app to "In production", Gmail sender display name, UptimeRobot label).
6. No migration. Tests unchanged and passing.
7. THIS PR STOPS FOR MY REVIEW. Do NOT enable auto-merge. When the five checks are green, tell me the PR number and wait.
```
