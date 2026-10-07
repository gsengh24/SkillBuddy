# Cynergi design spec (v1)

Status: approved direction, 7 October 2026. Replaces Skill Buddy's current UI. Frontend only. No backend or API change.

Reference files that sit next to this spec (match them visually, they are the source of truth for "exact same output"):
- `reference-landing.html` : the landing page, responsive (open it, then narrow the window to see the phone layout).
- `reference-home.html` : the merged Home page, responsive (two columns on desktop, one column on phone).

If this spec and the reference HTML disagree, the reference HTML wins for how it looks, and this spec wins for behaviour, accessibility and constraints.

---

## 1. Principles

1. Light theme, white ground, near-black ink, English green as the single brand colour.
2. Very bold, polished, professional. Heavy tight headlines, hairline borders, generous space.
3. Structure copied from the LocalCan inspiration (bordered rounded panels, visible hero grid, numbered sections, black label chips, FAQ accordion, CTA band, multi-column footer). Type feel copied from the "Find your people" inspiration (two-tone headlines, bold lead word plus muted rest, hairline dividers).
4. Nothing from LocalCan's brand is reused: no wording, no logos, no customer logos, no testimonials, no photos, no pricing, no receipts.
5. Fast. Animate only `transform` and `opacity`. No animation library. No layout shift.
6. Same design on desktop and phone. Phone is designed first; desktop adds columns.

## 2. Tokens

Define once as CSS variables on `:root` (and mirror in the Tailwind or CSS config the repo uses). Components only use tokens, never raw hex.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#FFFFFF` | page |
| `--panel` | `#F6F7F5` | cards, composer, inactive segments |
| `--line` | `#E4E6E2` | hairline borders and dividers (1px) |
| `--line-strong` | `#D9DBD6` | outer frames |
| `--ink` | `#0A0A0A` | primary text, primary button |
| `--ink-2` | `#4A4F4A` | body text |
| `--muted` | `#6B6F6A` | muted text that must stay readable (4.5:1 on white) |
| `--muted-2` | `#8A8F89` | second half of two-tone headlines and stat numerals, large bold text only (24px bold and up). NEVER for small text, times, counters, placeholders or labels: use `--muted` there |
| `--faint` | `#B0B4AE` | section numerals 01, 02, 03: decorative, `aria-hidden`. If axe still flags them in Smoke, darken the colour until it passes, do not exempt them |
| `--green` | `#0F4A34` | brand: links, outline buttons, eyebrows, CTA band |
| `--green-hover` | `#0B3828` | hover and pressed |
| `--green-tint` | `#E8F1EC` | hero panel, soft badges |
| `--green-line` | `#B9D3C5` | borders inside green tint areas |
| `--green-soft` | `#F3F9F5` | chip fill on tint |
| `--mint` | `#7BE0A8` | pixel art fills and dots only. Never as text on white. |
| `--mint-text` | `#9FD1B6` | second line of headline on the green CTA band |
| `--danger` | `#B3261E` | errors, report and block confirmations |

Radii: panels 14px, cards 12px, inputs and buttons 9px, small chips 4px, pills 99px.
Borders: 1px solid `--line` (use `0.5px` only on high-density screens if it renders crisply).
Spacing scale: 4, 8, 12, 16, 20, 24, 32, 48, 72. Content max width 1160px. Side gutter 16px on phone, 32px on desktop.
No shadows except the focus ring. Focus ring: `0 0 0 2px #fff, 0 0 0 4px var(--green)`.

Dark mode: not in v1. Keep all colours in tokens so it can be added later.

## 3. Typography

Self-host through `next/font` (the CSP and the privacy page rule out Google Fonts at runtime). Subset to Latin.

| Role | Font | Weight | Notes |
|---|---|---|---|
| Display headlines | Inter Tight (or Geist if Inter Tight is unavailable) | 800 | tracking -0.045em to -0.05em, line-height 1.0 to 1.05 |
| Body and UI | Inter | 400 and 500 | line-height 1.5 |
| Labels, numerals, chips, counters | JetBrains Mono (or Geist Mono) | 400 and 500 | small caps style via uppercase and letter-spacing .06em |

Scale (phone / desktop):
- Hero headline: 32px / 64px
- Section headline: 26px / 48px
- Row titles and people's names (list rows, chat header): 14px, weight 600 (medium-bold, not 800), tracking -0.01em
- Card titles inside panels: 14px 600 / 16px 600. Weight 800 is only for display headlines, stats numerals and lead words in the numbered rows
- Body: 14px / 16px
- Small and metadata: 12px / 13px
- Mono labels: 10px / 11px

Two-tone headline rule: first sentence in `--ink`, remainder in `--muted-2`. Keep to two lines of colour at most.
Lead-word rows: the lead word is 800 weight in `--ink`, the rest is regular in `--muted-2`, separated by 1px `--line` rules.
Sentence case everywhere in the UI. No Title Case, no ALL CAPS except mono labels.
Use contractions. Active voice. Button labels: verb first, 1 to 3 words, no full stop.

## 4. Components (build these first, in PR 1)

1. **Button**: `primary` (ink fill, white text), `outline` (green border and text, transparent fill), `ghost`. Height 40px phone and desktop, 36px compact. Hover lifts 2px (transform). Active scales .97. At most one primary per view.
2. **Keycap chip**: NOT in v1. No "S" or "D" chips and no single-key shortcuts. This avoids a new setting and screen-reader conflicts. Maybe later.
3. **Panel**: white or `--panel`, 1px `--line`, radius 14px, padding 16 phone / 24 desktop.
4. **Hero grid**: bordered cells, 1px `--green-line`, on `--green-tint`. Cells hold real product pieces only.
5. **Label chip**: black fill, white mono text, 10px, radius 4px, with a leading `*`. Used on cards.
6. **Topic chip**: pill, 1px green border, green mono text, white fill.
7. **Badge**: `REQUEST` (black), `INTRO` (green tint with green text and green-line border).
8. **Segmented control**: `--panel` track, white selected segment with 1px line. Used for All, Requests, Messages.
9. **List row**: 34px leading icon or avatar, title 14px weight 600, one-line secondary text 12px, optional right-side badge or unread dot. Rows separated by 1px lines, not cards.
10. **Avatar**: circle with initials, `--green` or `--ink` fill, white text. No photos.
11. **Input and textarea**: white, 1px `--line`, radius 10px, 16px text on phone (prevents iOS zoom), green focus ring, character counter in mono.
12. **Accordion** (FAQ): hairline rows, chevron rotates 180deg, height opens with `grid-template-rows` transition, one open at a time optional.
13. **Skeleton**: `--panel` blocks with a slow opacity pulse, used by `loading.tsx` on every route.
14. **Numbered feature row**: mono numeral in `--faint`, then the lead-word text.
15. **CTA band**: `--green` fill, white 800 headline with the second half in `--mint-text`, white button, optional static pixel pattern in the right corner.
16. **Footer**: 1px top rule, brand and one-line description left, link columns right, legal row at the bottom.
17. **Pixel pattern**: a small static SVG of squares in `--mint` and `--green`, decorative, `aria-hidden`. No canvas.
18. **Bottom nav** (phone): 4 items, icon 20px plus 10px label, active item in `--green`, safe-area padding.
19. **Top bar** (desktop): logo left, links, Sign in (ghost), Get started (primary).
20. **Toast and inline error**: sentence case, say what happened and what to do, no "Error:" prefix.

## 5. Motion

- Page sections fade up once (opacity 0 to 1, translateY 8px to 0, 450ms ease) when they enter the viewport. One shared `useInView` hook (IntersectionObserver). Do not re-trigger.
- Hero grid cells fade up one after another on load, 70ms apart, 8 cells maximum.
- Buttons: translateY(-2px) on hover (desktop only), scale(.97) on press.
- Panels and rows: border colour changes to `--green-line` on hover (desktop only).
- Accordion opens smoothly.
- Route change: the `loading.tsx` skeleton shows immediately.
- Nothing moves continuously while scrolling. No parallax. No autoplay video.
- `@media (prefers-reduced-motion: reduce)`: all of the above off, content simply appears.
- Only `transform` and `opacity`. No `will-change` except on elements that are animating.

## 6. Pages

### 6.1 Landing (public), see `reference-landing.html`
Sections in order:
1. Top bar.
2. Hero panel on `--green-tint`. Left: mono eyebrow chip "for builders, learners, explorers", headline **Say what you're building.** / *Meet who can help.* (second half muted), one-sentence body, buttons "Find your people" (primary) and "See how it works" (outline). Right (desktop) or below (phone): the hero grid with cells: topic chip "cybersecurity", people icon, "Why this match" card, pixel pattern, "Intro sent" state.
3. How it works: mono label, headline **Skills. Interests. Intent.** / *Matched.*, then three lead-word rows (Skills, Interests, Intent) numbered 01 to 03.
4. Three cards with black label chips: Safe by default, Human chats, Pair spaces. Do not say "one tap" (reporting asks for a reason): use "Block or report from any chat." Copy must match `/privacy` and the "no AI in chats" promise exactly. Do not claim anything the privacy page does not say.
5. FAQ accordion. Answers are drafted from `docs/` and `/privacy`. Privacy answers stop for owner review.
6. CTA band: **Your next collaborator** / *is one sentence away.*
7. Footer: Privacy, Terms, Contact (the address in `frontend/lib/legal.ts`). Legal row is "© 2026 Cynergi" only, with no "All rights reserved" until the lawyer approves.

Dropped on purpose until real: customer logos, quotes, testimonials, pricing, comparison receipts, world map.

### 6.2 Home (signed in), see `reference-home.html`
Requests and Messages are now one page. The old Messages route redirects to Home.

Phone (single column):
1. Header: "Home" (800), bell icon.
2. Greeting: mono label ("Good morning", "Good afternoon" or "Good evening" from the device clock, set in the browser after load so the server's UTC clock never shows the wrong one; the first paint says "Hello"), then a two-tone display headline "What are you building today?" / "Say it in a sentence." (second line muted).
3. New request composer on `--green-tint` with green-line border: mono label NEW REQUEST, textarea, counter (500 max, as today), primary "Find people", and four suggestion pills under it (examples such as "a design partner", "learn React"). Tapping a pill fills the textarea with that phrase, it never sends anything. Suggestions are static text for now, not AI-generated and not based on user data.
4. Summary strip: three bordered cells with a large 800 numeral and a mono label (Requests, Messages, Spaces). Numbers come from the data already fetched, no new endpoint.
5. Mono label "Recent activity", then the segmented filter: All (default), Requests n, Messages n.
6. One list, newest activity first, rows separated by hairlines. Each row shows a mono relative time on the right ("2m", "12m", "1h", "Yesterday") next to the badge or unread dot:
   - Request row: search icon tile, request title, "n matches ready to view", REQUEST badge. Opens the matches for that request.
   - Intro received row: dashed tile with user-plus icon, "New intro received", what they asked for, INTRO badge. Opens the intro (accept, decline, block, report).
   - Message row: avatar initials, name (only shown once connected, as today), a one-line status, and an unread dot. Opens the chat. The status is "n new messages" when `unread_messages` is above 0, otherwise "Open chat". The API does not send message text, so there is NO message preview in v1 (no extra calls, no backend field). The time comes from `last_message_at`.
7. Green band under the list with a static pixel pattern: "Turn a connection into a shared goal." and a white "Open pair spaces" button. Hide it when the user has no connections yet.
8. Bottom nav: Home, Spaces, Saved, You.

Desktop (two columns, left 380px list, right flexible detail):
- Left: composer, filter, list. Right: the opened thing (matches, intro, or chat), or an empty state that invites a first request.
- The route stays `/home`. Keep `/messages/[id]` as the chat page (deep links and report flows use it) and make `/messages` redirect to `/home`. Opening an item sets `?item=<type>-<id>` so back and refresh work. On phone the same URL shows the detail full screen with a back arrow.

Rules:
- Names and links stay hidden until the connection exists. Do not change this.
- Block and report stay inside the chat, the intro and the match card, exactly as built. Restyle only. Those screens are legal-sensitive (see section 9).
- "Open pair space" button stays on a connected person's row and chat header.
- Data comes from the existing endpoints only (`/auth/me`, `/me/profile`, `/requests`, `/intros?box=received`, `/connections`, `/messages/updates`, `/notifications/unread-count`). Fetch them in parallel (`Promise.all`), never one after another. Do not add endpoints.
- Empty state: headline "Start your first request", one line of body, button "Find people".
- Error state: one sentence, then a "Try again" button.

### 6.3 Other app pages (restyle with the same components)
Matches and the intro form, chat, Pair spaces list, a pair space, Profile, Settings (account, emails, blocked people), Saved, You, sign in, 404 and error. Moderation pages (queue, AI status, suspended accounts): restyle last, same components, functional first.

## 7. Responsive rules
- Breakpoints: phone below 640px, tablet 640 to 1023px (single column, wider gutter), desktop 1024px and up.
- Touch targets at least 44px high.
- Inputs 16px on phone.
- No horizontal scrolling anywhere.
- Test at 360, 390, 768, 1024, 1280 and 1536px widths.

## 8. Accessibility
- Text contrast at least 4.5:1 (3:1 for 24px+ bold). `--muted-2` and `--faint` are only for large or decorative text.
- Visible focus ring on every control. Keyboard order follows visual order.
- Accordion, segmented control, bottom nav and list rows use correct roles and `aria-current` or `aria-expanded`.
- Decorative icons and the pixel pattern are `aria-hidden`.
- Reduced motion respected.
- Colour is never the only signal (unread dot also gets a text or screen-reader label).
- Item 30 (NVDA and TalkBack pass) stays an owner task after the redesign.

## 9. Constraints from the existing project
- Design rules: ADR 0010 and the design rules in CLAUDE.md ban motion, allow outline buttons only and require `personHue()` colours. They conflict with this spec. PR 1 adds ADR 0014 (replaces 0010), updates the design rules in CLAUDE.md, and updates the token and contrast tests to the new values. Contrast tests must still enforce the same minimum ratios on the new colours. Motion is allowed only as described in section 5. Avatars use `--green` or `--ink`, chosen by a stable hash of the person's id.
- Existing Smoke tests (`security.spec`, `social.spec`, `login.spec`, `discover.spec`) expect the old headings and tab names. Update only their expected text for the new Home and nav, nothing else.
- CSP and HSTS stay as they are (the CSP already allows the inline scripts Next.js itself needs; do not loosen it). Write no hand-made inline scripts. Self-hosted fonts and own-domain images only. No external fonts, CDNs or analytics. Smoke fails on any CSP violation, so check it on the preview.
- Performance: keep each route's first-load JS small, avoid large images, use SVG and CSS for art, and do not make pages slower than today. Report the bundle size per page before and after each PR.
- Legal-sensitive screens: privacy, terms, consent, report, block, moderation, `frontend/lib/legal.ts`, `TERMS_VERSION`. A restyle PR touching these stops for the owner's review, no auto-merge.
- No backend change. No migration. `docs/api/openapi.json` must not change.
- Every PR: five required checks green, no weakened tests, short-lived branch, one PR per change, no secrets.

## 10. Brand and rename
- Name: **Cynergi** (lowercase `cynergi` in the wordmark). Define it once in a single brand constant (name, tagline, contact address source) and import it everywhere.
- Logo: the supplied file has spaces and "WhatsApp" in its name, so save it as `docs/design/cynergi-logo-source.jpeg`. The real logo, once vector, goes to `frontend/public/logo.svg`. The supplied logo is teal and lavender on dark plum, which does not match the palette. Until a vector file arrives, use a placeholder four-dot mark in `--green` and `--ink` plus the wordmark in Inter Tight 800, lowercase, tracking -0.04em. Keep the logo in one component so it can be swapped for the real SVG in one place.
- Rename only what users see: page titles, metadata, favicon and app icons, docs. Email names and subjects come from the backend `app_name` setting: the owner sets `APP_NAME=Cynergi` in Render (no repo change). The OpenAPI title and `docs/api/openapi.json` stay as they are until a separate small backend PR. Keep the repo, Render service and Vercel project names for now.
- ADRs keep their history, with a one-line note that the product was renamed.
- Privacy and terms: the name change is a legal-wording PR. New `TERMS_VERSION`. Stops for the owner's review.
- Check cookie and storage key names. Do not rename them without telling the owner (renaming signs everyone out; fine on staging).
- Owner does the dashboard steps: Google OAuth consent screen name and logo (before setting the app to "In production"), Gmail sender display name, UptimeRobot label.

## 11. Taglines
- Hero: **Say what you're building. Meet who can help.**
- How it works: **Skills. Interests. Intent. Matched.**
- CTA: **Your next collaborator is one sentence away.**
- Spare: "Meet people worth building with.", "Find the person, not the profile.", "Synergy, on purpose."

## 12. Definition of done (every PR)
1. Matches the reference HTML at 390px and 1280px wide (side-by-side screenshots in the PR).
2. Five checks green. Smoke shows no CSP violation.
3. Keyboard and reduced-motion checked.
4. Bundle size per page reported.
5. Legal-sensitive PRs stop for the owner.
