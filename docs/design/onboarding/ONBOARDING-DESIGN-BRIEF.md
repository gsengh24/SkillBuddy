# Cynergi: onboarding redesign brief (for mockups)

Paste this whole file into a Claude chat and ask it to generate the screens in section 6.
It's self-contained: product context, the problem, the design system, and every screen and
state to draw. For a closer visual match, also attach the screenshots in
`docs/design/screenshots/home-v2-pr4b/` and `docs/design/reference-home.html`.

---

## 1. What you're making

High-fidelity UI mockups of a **new onboarding flow** and the screens around it for
**Cynergi**, a web app (responsive, phone-first) that introduces university students to
collaborators, skill partners and interest buddies.

**Output format**
- One self-contained HTML file per screen (inline CSS, no JavaScript frameworks needed;
  small inline JS only for simple interactions like chip toggling).
- Show every screen at **two widths side by side or one after another: phone 390px and
  desktop 1280px.**
- Fonts may load from Google Fonts *in the mockup only* (Inter Tight, Inter, JetBrains
  Mono). The real app self-hosts them.
- Use only the colour tokens in section 4, as CSS variables on `:root`. No other colours.
- Use synthetic people and data only (see section 8).

---

## 2. Product context

- **Name:** Cynergi (always lowercase `cynergi` in the logo wordmark).
- **Tagline:** "Find the people worth building with."
- **Description:** "Describe who you are and what you want to do. We introduce you to the
  few people worth talking to, and tell you why."
- **Audience:** students at Thapar Institute (Patiala, India), 18+, signed in with an
  `@thapar.edu` Google account or an email code.
- **How it works:**
  1. You build a profile (skills, interests, what you offer, what you want).
  2. You post a request in one sentence ("a designer for my app") and choose an intent.
  3. The system finds a few matching people and shows up to 5 **anonymous** match cards,
     each with a one-line reason why.
  4. You send an intro note. The other person accepts (then names show and chat opens) or
     declines (you're never told).
- **Six intents** (used everywhere, keep exact labels):
  Build together · Skill exchange · Interest buddy · Accountability · Mentor · Explore
- **App navigation:** desktop top bar and phone bottom nav have three places:
  **Home** (requests and messages together), **Spaces** (pair spaces and teams), **You**
  (profile and settings). The phone top bar also has the logo, a bell with an unread dot,
  and an account circle.
- **Values shown in the product:** two-sided consent, privacy by default (names hidden
  until both agree), no AI in chats, few good matches instead of many.

---

## 3. The problem this redesign solves

After signing in, most users never finish their profile, so most accounts are empty and
dormant. Today's onboarding is "Step 1 of 2: Tell us about you", a single **blank
2,000-character "About you" textarea** plus name, links and languages, then a "check what we
understood" step. People don't want to write a bio before they've seen any value.

**Design goals**
1. A profile in **under 60 seconds with almost no typing**: tap chips, not paragraphs.
2. **Value before effort:** let people say what they want first, and show that real people
   are here.
3. **One-click shortcuts:** import from a resume PDF or pasted text.
4. **Gradual completion:** start small, ask one more thing at the right moment later.
5. **Bring dormant users back** with a reason to return.

---

## 4. Design system (match exactly)

The app is a **dark theme**. Bold, polished, professional: heavy tight headlines, hairline
borders, generous space, a single green brand colour. No shadows except the focus ring.

### 4.1 Colour tokens

| Token | Hex | Use |
| --- | --- | --- |
| `--bg` | `#0B0C0B` | page background |
| `--page-soft` | `#171917` | page background on Home, Spaces and You (cards sit darker) |
| `--panel` | `#141614` | cards, composer, inactive segments |
| `--card` | `#111311` | surface of cards and text boxes |
| `--line` | `#262826` | 1px hairline borders and dividers (never a control's only edge) |
| `--line-strong` | `#323532` | outer frames |
| `--ink` | `#F3F4F1` | primary text and the primary button fill |
| `--ink-hover` | `#FFFFFF` | primary button hover |
| `--ink-2` | `#C9CCC6` | body text |
| `--muted` | `#A9ADA7` | secondary text (readable, 4.5:1) |
| `--muted-2` | `#8A8E88` | second half of two-tone headlines (large bold only) and **field borders** |
| `--faint` | `#4A4D49` | decorative only, never text |
| `--green` | `#7BE0A8` | brand: links, outline buttons, eyebrows, selected chips, CTA band |
| `--green-hover` | `#9FD1B6` | hover and pressed |
| `--green-tint` | `#142219` | hero panels, composer, soft badges, selected row |
| `--green-line` | `#2A4536` | borders inside green-tint areas |
| `--green-soft` | `#101A14` | chip fill on tint |
| `--mint` | `#7BE0A8` | pixel-art fills and dots only, never text |
| `--danger` | `#FF8A80` | errors |
| `--amber` | `#E8A06F` | "needs a reply" accents |

On the **green CTA band** (fill `--green`): headline text `#0B0C0B`, its second half
`#256040`, button dark.

### 4.2 Typography

| Role | Font | Weight | Notes |
| --- | --- | --- | --- |
| Display headlines | Inter Tight | 800 | tracking −0.03em (−0.04em from 56px up), line-height 1.02–1.05 |
| Body and UI | Inter | 400 / 500 | line-height 1.5 |
| Labels, numerals, chips, counters | JetBrains Mono | 400 / 500 | uppercase, letter-spacing .06em |

Scale (phone / desktop): hero 32 / 64px · section headline 26 / 48px · page headline
30 / 44px · row titles and names 14px weight 600 · card titles 14 / 16px weight 600 ·
body 14 / 16px · small 12 / 13px · mono labels 10 / 11px.

**Two-tone headline:** first sentence in `--ink`, the rest in `--muted-2`, at most two
lines of colour. Example: "Tell us what you're into." / "Tap, don't type."

### 4.3 Shape and layout

- Radii: panels 14px, cards 12px, buttons 9px, inputs 10px, small chips 4px, pills full.
- Borders: 1px solid `--line`. Inputs use 1px `--muted-2`.
- Spacing scale: 4, 8, 12, 16, 20, 24, 32, 48, 72.
- Content max width 1160px; side gutter 16px phone, 32px desktop.
- Breakpoints: phone < 640, tablet 640–1023 (single column), desktop ≥ 1024.
- Touch targets at least 44px tall on phone. Inputs use 16px text on phone.
- No horizontal scrolling at any width.

### 4.4 Components to reuse

- **Button:** `primary` (ink fill, dark text; **at most one per view**), `outline` (green
  border and text, transparent), `ghost`. 40px tall. Labels verb-first, 1–3 words, no full
  stop.
- **Panel:** `--panel`, 1px `--line`, radius 14, padding 16 phone / 24 desktop.
- **Topic chip (pill):** 1px green border, green mono text. **Selected:** filled
  `--green` with dark text and a small dot. Unselected chips have a small green dot.
- **Label chip:** small black/ink chip, mono 10px, radius 4, leading `*`.
- **Badge:** `REQUEST` (ink) and `INTRO` (green tint, green text, green-line border).
- **Segmented control:** `--panel` track, raised selected segment with 1px line.
- **List row:** 34px leading icon or avatar, 14px/600 title, 12px one-line secondary text,
  optional badge or unread dot; rows split by 1px lines, not cards.
- **Avatar:** circle with white initials on green (`#0F4A34`) or ink (`#2B2D2B`). No photos
  except a person's Google account picture.
- **Input/textarea:** dark card fill, 1px `--muted-2` border, radius 10, green focus ring,
  character counter in mono at the bottom right ("0 / 500").
- **Progress:** mono label "STEP 2 OF 4" plus a thin 4-segment bar in green / `--line`.
- **Meter:** "Profile strength" bar with a percentage numeral (800 weight) and a list of
  missing items as links.
- **Accordion:** hairline rows, chevron rotates 180°.
- **CTA band:** `--green` fill, two-tone dark headline, small static pixel pattern of
  squares in the corner (decorative).
- **Skeleton:** `--panel` blocks with a slow opacity pulse.
- **Toast and inline error:** sentence case, say what happened and what to do; no
  "Error:" prefix.

### 4.5 Motion

Only `transform` and `opacity`, once. Sections fade up 8px over 450ms. Buttons lift 2px on
hover (desktop) and scale to .97 when pressed. Chips can scale briefly when selected. No
parallax, no looping animation. Everything off with `prefers-reduced-motion`.

### 4.6 Accessibility

Text contrast 4.5:1 (3:1 for 24px+ bold). Visible green focus ring
(`0 0 0 2px var(--bg), 0 0 0 4px var(--green)`). Colour is never the only signal. Chips
are toggle buttons (`aria-pressed`). Decorative art is `aria-hidden`.

### 4.7 Voice and copy

Sentence case everywhere (no Title Case; ALL CAPS only in mono labels). Contractions,
active voice, short sentences, friendly but not cute. No emoji in the UI. Never promise
anything about privacy beyond what's stated in section 7.

---

## 5. The new onboarding flow

```
Sign in → [1] What are you here for → [2] What you offer → [3] What you want
        → [4] A bit about you → [5] Check what we understood → Home (first request)
                     ↘ shortcut on step 2: Import from resume / Paste anything
```

Steps 1–4 are taps only. Free text is always optional. Every step has a "Skip for now" ghost
link except step 1. A thin progress bar and "STEP n OF 4" sit at the top. The primary
button is "Continue"; the last one is "Finish".

From the chips, the system writes a short "about" text for the matcher, for example
*"Offers: React, Figma. Wants: a backend partner. Into: chess, hackathons."* The person can
edit it on step 5.

---

## 6. Screens to generate

Generate each at 390px and 1280px. On desktop, centre onboarding in a 640px column with the
logo top left and "Step n of 4" top right; no app nav during onboarding.

### Screen 1: What are you here for? (step 1 of 4)
- Mono eyebrow: "WELCOME TO CYNERGI"
- Two-tone headline: **"What brings you here?"** / *"Pick all that fit."*
- Six large selectable cards (2 columns on phone, 3 on desktop), one per intent, each
  with a simple line icon, the label and one line:
  - Build together: "Find people to make a project with."
  - Skill exchange: "Teach what you know, learn what you don't."
  - Interest buddy: "Someone to share a hobby with."
  - Accountability: "A partner to keep each other on track."
  - Mentor: "Learn from, or guide, someone further along."
  - Explore: "Just see who's out there."
- Show two cards selected.
- Social-proof line under the cards, mono, muted: "128 STUDENTS JOINED THIS MONTH"
  (aggregate count only).
- Primary "Continue" (disabled until one card is picked).

### Screen 2: What can you offer? (step 2 of 4)
- Headline: **"What are you good at?"** / *"Tap a few. You can change these later."*
- Search field with a magnifier: "Search skills, e.g. Python".
- Grouped chip clouds with mono group labels: CODING (Python, Java, C++, React, Node.js,
  Flutter, Android, Machine learning, Data analysis, SQL), DESIGN (Figma, UI design,
  Graphic design, Video editing, 3D modelling), BUILD (Arduino, Robotics, CAD, PCB
  design), OTHER (Public speaking, Writing, Marketing, Finance, Photography, Music). Show
  5 selected.
- **Shortcut panel** at the top, on `--green-tint`: "Skip the typing" + two outline
  buttons, **"Import resume (PDF)"** and **"Paste text"**, with a muted note:
  "Your file is read in your browser and isn't uploaded."
- Footer: "Skip for now" (ghost), "Continue" (primary), selected count in mono:
  "5 SELECTED".

### Screen 3: What do you want? (step 3 of 4)
- Headline: **"What are you looking for?"** / *"Skills you want to learn or find."*
- Same chip layout, separate selection (show 3 selected).
- Optional single-line input below: "Anything specific? (optional)" with placeholder
  "e.g. a designer for my app, a gym partner for mornings", counter "0 / 140".
- Interest chips section: INTERESTS (Chess, Hackathons, Startups, Gaming, Fitness,
  Reading, Music, Open source, Competitive programming, Debate). Show 2 selected.

### Screen 4: A bit about you (step 4 of 4)
- Headline: **"Almost done."** / *"A few quick details."*
- Year: segmented control (1st, 2nd, 3rd, 4th, Postgrad).
- Branch: select (Computer Engineering, Electronics and Communication, Electrical,
  Mechanical, Chemical, Civil, Biotechnology, Other).
- Availability: day chips Mon–Sun (Sat and Sun selected) and a segmented "Hours a week":
  1–2, 3–5, 6–10, 10+.
- Display name field, prefilled from the Google account ("Aarav S.").
- Primary "Finish".

### Screen 5: Check what we understood
- Mono label "YOUR PROFILE", headline **"Here's how others will see you."**
- A preview of the **anonymous match card** others see: no name, a short heading
  ("Frontend builder looking for a backend partner"), one sentence, topic chips, the
  intents, and availability ("Weekends · 3–5 h/week").
- Below: an editable "About you" textarea prefilled with the generated text, counter
  "86 / 500".
- **Loading variant:** a skeleton card with "Reading your profile…" (understanding the
  profile runs in the background and takes a few seconds).
- **Fallback variant:** if the AI is unavailable, show the card built from the chips only,
  with a muted note "We'll polish this shortly." (never an error).
- Primary "Looks good"; ghost "Edit".

### Screen 6: Resume import
Three states in one file:
1. **Pick:** dashed drop area on `--card`: "Drop your resume PDF here or choose a file",
   a note "Up to 2 MB. Read in your browser, never uploaded or stored.", and a help
   accordion **"Using LinkedIn?"** → "Open your LinkedIn profile, choose More → Save to
   PDF, then drop that file here."
2. **Reading:** progress with "Reading your resume… We remove phone numbers, emails and
   addresses before anything else happens."
3. **Suggestions:** "We found these. Keep what's right." Chip groups (Skills you offer,
   Interests, Projects) with suggested chips pre-selected and an ✕ on each; a "Use these"
   primary button.

### Screen 7: Paste anything
- Headline: **"Paste anything about you."** / *"LinkedIn About, resume, a portfolio blurb."*
- Large textarea, counter "0 / 2000", note "We pick out skills and interests. You'll
  confirm everything."
- Primary "Find my skills". Then the same suggestions state as screen 6.

### Screen 8: Home with an unfinished profile
Use the existing Home layout (desktop: 360px inbox pane on the left, composer on the
right; phone: single column with bottom nav Home / Spaces / You).
- Replace the empty inbox with a **"Finish your profile"** panel on `--green-tint`:
  meter at 40%, "3 quick steps left", primary "Finish in 60 seconds".
- Social proof under it, aggregate only: "23 people are looking for Python skills this
  week. Finish your profile to be matched."
- The composer still works ("What are you building today?" / "Say it in a sentence.").

### Screen 9: Soft gate dialog
A modal shown when someone without a profile tries to send an intro or join a team:
- Title: "Add 3 skills first"
- Body: "People decide whether to accept based on your profile. It takes under a minute."
- Inline chip picker (show 1 of 3 selected), counter "1 / 3", primary "Save and continue",
  ghost "Not now".

### Screen 10: You page, profile strength
The You page header card: initials avatar, name, headline, city, **profile strength meter
(65%)** with missing items as links ("Add availability", "Add a link", "Add what you're
looking for"), and an outline "See how others see you" button. Show the numbered section
list on the left (desktop) or a sticky chip row (phone): 01 Basics, 02 Skills, 03 Looking
for, 04 Availability, 05 Links, 06 Privacy and visibility, 07 Alerts, 08 Account and
security, 09 Your data, 10 Danger zone.

### Screen 11: In-context nudge
A small dismissible card on Home, used after an event: "You joined the ML space. Add
Machine learning to your skills?" with "Add" (outline) and "Dismiss" (ghost). Also a
second variant after a first match: "Add your availability so people know when you're
free."

### Screen 12: Re-engagement email
A plain, light-on-dark-safe HTML email (600px wide, inline styles, no images except the
wordmark in text):
- Subject: "3 people are looking for skills like yours"
- Body: "People at Thapar are looking for Python and React skills this week. Finish your
  Cynergi profile in about a minute to be considered."
- One button: "Finish my profile". Footer: "You're getting this because email alerts are
  on. Turn them off in You → Alerts."
- Show a second variant for day 10 (the last one): "We'll stop reminding you after this."

---

## 7. Hard rules for content (do not break)

- **Never show a person's name, photo or contact details on a match card or suggestion.**
  Names appear only after both people accept an intro.
- **Social proof is aggregate counts only** ("23 people…"), never names, avatars or
  quotes. No testimonials, no fake reviews, no university or company logos.
- **No file is uploaded or stored.** Resume text is read in the browser, personal details
  are removed, and only confirmed skills and interests are saved.
- **AI wording:** the AI reads profile text to suggest skills and matches. Never say the AI
  reads chats (it doesn't).
- Any privacy, consent or email-preference wording in these mockups is a **draft for the
  owner to review**; mark it with a small "Draft copy" note in the mockup's margin.
- 18+ only; don't depict anyone as a minor.
- Limits to respect in counters: name 60, headline 80, about 500 on You (2,000 raw),
  goal 300, request 1,000, up to 3 links.

---

## 8. Sample data (synthetic)

- People: Aarav S., Meher K., Ishaan P., Simran B., Kabir T. (initials avatars only).
- Requests: "A designer for my expense-tracker app", "Someone to practise DSA with
  three evenings a week", "A partner for the next hackathon (ML track)".
- Match reason example: "Both into ML hackathons; they build backends in FastAPI and want
  a frontend partner."
- Spaces: "ML study circle", "Weekend app builders".

---

## 9. What "done" looks like

- Every screen in section 6 at 390px and 1280px, dark theme, tokens only.
- Selected and unselected chip states, disabled and enabled buttons, focus ring visible on
  at least one control per screen.
- Loading, empty and fallback states where listed.
- It looks like one product with the existing Home page: same nav, type and spacing.
