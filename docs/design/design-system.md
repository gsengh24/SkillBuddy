# Skill Buddy design system: direction B, "Quiet dashboard"

> **Superseded** by the Cynergi design ([ADR 0014](../adr/0014-design-system-cynergi.md),
> [design-spec.md](design-spec.md)). This page still describes the older components in
> `frontend/components/ui`, which existing screens use until they are restyled.

Chosen by the owner on 2026-10-02 ([ADR 0010](../adr/0010-design-system-quiet-dashboard.md)).
Visual references: [desktop](reference/desktop.png) and [phone](reference/phone.png).

**Where it lives:**
- Tokens: `frontend/lib/design/tokens.ts`, which is the source of truth, mirrored in the
  Tailwind theme in `frontend/app/globals.css` (a test keeps the two identical).
- Components: `frontend/components/ui/`.
- App shell: `frontend/components/shell/`.
- Living style guide: `/design`, in development only; production builds answer 404.

## Brief

Calm, light green and white, with soft colour. Thin outlined controls, never bulky filled
buttons. **No animations or transitions**: hover and focus change colour only. Desktop and
phone are equal priorities.

## Tokens

### Neutrals

| Token | Hex | Tailwind |
| --- | --- | --- |
| ground | `#F2F6F0` | `bg-ground` (page background) |
| paper | `#FBFDF9` | `bg-paper` (cards, sidebar) |
| ink | `#14201A` | `text-ink`, `border-ink` |
| muted | `#55655B` | `text-muted`, field underlines |
| line | `#D3DCD1` | `border-line` (dividers, card borders) |
| line-strong | `#B9C7B8` | `border-line-strong` (disabled outlines) |

### Hues

Each hue has the following roles:
- **base:** dots, bars and fills only, never text;
- **ink:** text;
- **tint:** backgrounds;
- **edge:** borders of tags;
- **track:** the unfilled part of a bar.

| Hue | base | ink | tint | edge | track |
| --- | --- | --- | --- | --- | --- |
| green | `#2C6A4C` | `#1F5238` | `#E1F0E4` | `#C5D8C8` | `#C7D8CE`* |
| amber | `#D08A1E` | `#6E4608` | `#FDF3DC` | `#EBD2A8`* | `#F3DFB2` |
| coral | `#E2573E` | `#9A3B27` | `#FBE4DD` | `#F0BFB2` | `#F6D4CB` |
| blue | `#3F78B5` | `#2A5683` | `#E0ECF8` | `#B5CCE0`* | `#CCDCE8`* |
| violet | `#7B63C2` | `#54428F` | `#ECE6F7` | `#D2C7EA` | `#DFD6F1` |
| teal | `#1F8A8C` | `#1B6466` | `#DDF0EF` | `#B5DCDA` | `#C8E5E3` |

\* Not in the brief; derived by mixing the base into paper at the same strength as the
given values (edge about 37%, track about 25%). The green edge is the brief's chip-edge.

Green-only surfaces: panel `#DDEFE1` (hero panel), chip `#EDF6EE`, chip-edge `#C5D8C8`
(unselected intent chips).

**Badge:** fill `#B83D28` with paper text. This is a darker coral, because the coral base
(`#E2573E`) under paper text is only 3.71:1. The badge reaches 5.49:1.

In components, a hue is applied with `hueStyle(hue)` (from `lib/design/color.ts`), which
sets `--hue-base`, `--hue-ink`, `--hue-tint`, `--hue-edge` and `--hue-track`. Classes then
read them, for example `bg-(--hue-tint) text-(--hue-ink)`.

### Intents

| Intent | Hue |
| --- | --- |
| Build together | green |
| Skill exchange | amber |
| Interest buddy | coral |
| Accountability | blue |
| Mentor | violet |
| Explore | teal |

### A person's colour

`personHue(userId)` picks one of the six hues with a stable hash (FNV-1a) of the user id.
**Never tie colour to any personal attribute** (gender, year, branch, skills, anything).
The function takes the id and nothing else.

### Type

Fonts come from `next/font`. They are downloaded at build time and served by the app, so
nothing is fetched from a font CDN at runtime.

| Use | Font | Size / weight | Tailwind |
| --- | --- | --- | --- |
| Heading 1 | Manrope | 28 / 700, -0.02em | `text-h1` |
| Section heading | Manrope | 19 / 700 | `text-section` |
| Body | Manrope | 14.5, line-height 1.6 | `text-body` (default) |
| Small | Manrope | 13, line-height 1.5 | `text-small` |
| Labels | IBM Plex Mono | 11 / 500, uppercase, 0.09em | `font-mono text-label uppercase` (`Overline`) |
| Numerals | Manrope | 33 / 800, -0.03em | `text-numeral` |

Manrope is loaded at 400–800 and IBM Plex Mono at 400 and 500.

### Radii

| Element | Radius | Tailwind |
| --- | --- | --- |
| Card | 18px | `rounded-card` |
| Hero panel | 22px | `rounded-hero` |
| Why-box | 12px | `rounded-why` |
| Chips, buttons, avatars | fully round | `rounded-full` |

## Components (`components/ui`)

| Component | What it is |
| --- | --- |
| `Button`, `ButtonLink` | Thin outline pill: 1px border, transparent fill. 44px high by default, 38px on large screens with a mouse. Tones: `ink` (default) and `danger` (coral ink). `hue` colours it with a person's ink (e.g. "Connect"). |
| `TextLink` | Underlined link in green ink (or `muted`). |
| `IntentChip` | Dot in the intent's base plus its label. Unselected: chip fill, chip-edge border. Selected: paper fill, border in the intent's **ink** (see contrast). With `onToggle` it is a toggle button with `aria-pressed`. |
| `Avatar` | Initials on the person's tint in its ink. Named (`role="img"`) unless `decorative`. |
| `StrengthBar` | Ticked bar (`repeating-linear-gradient`), track and fill in one hue; a `meter` with its value. |
| `MatchNumeral` | The big match number in the person's ink, with a small "%" and a spoken "match". |
| `WhyBox` | Tint background, radius 12, mono title in the hue's ink, body in ink. |
| `Tag` | Pill with the hue's edge border, ink text on paper. `TintPill`: tint fill with ink text (suggestions). |
| `Card` | Paper, 1px line border, radius 18. |
| `HeroPanel` | Green panel, radius 22, with the decorative pairing-rings motif (green, amber, coral, blue, violet). |
| `TextField`, `TextArea` | Underline-only (muted underline, green on focus), real `<label>`, hint and error wired to `aria-describedby`. |
| `Badge`, `BadgeDot` | Count badge in the darker badge coral with a spoken label; 99+ cap; nothing at zero. The dot is labelled, or hidden when its control already says so. |
| `Logo` | Two overlapping rings (green, amber) and the wordmark. |
| `Overline` | Mono uppercase label. |

## App shell (`components/shell`)

**Desktop (1024px and up):**
- **Sidebar (236px):**
  - logo;
  - Discover, Messages (with an unread badge), Saved and Pair spaces (a link since step
    9c, ADR 0013; on phones pair spaces open from each connection on Messages);
  - the profile-completeness card in amber;
  - the user block, at the bottom.
- **Main area**, with the notification bell at the top right.
- **Optional right rail (284px)**, shown from 1280px up. At 1024px there is no room for it
  beside the sidebar.

**Phone:**
- A top row with the logo and the bell.
- A fixed 64px bottom tab bar: Discover, Messages, Saved, You. Each tab is at least 44×44px.
- No fake status bar.

Signed-in pages live in the `app/(app)` route group, which wraps them in the shell. Messages,
Saved and Notifications are placeholders until their screens are built.

## Usage rules

1. **Only token colours.** Tailwind's default palette is removed, so a class like
   `bg-slate-50` does not exist. Add a token (in `tokens.ts` **and** `globals.css`) rather
   than an ad-hoc hex. The sync test fails otherwise.
2. **Never use a base colour for text.** Text on a tint uses that hue's ink. Base is for
   dots, bars, fills and decorative strokes.
3. **No motion.** No `transition-*` or `animate-*` classes. A global rule turns all
   animation and transition off, and hover and focus change colour only.
4. **Outline controls only.** No filled buttons. The only filled controls are chips, tabs and
   the active nav item, which use tints.
5. **Real elements.** Actions are `<button>`, navigation is `<a>`/`Link`. Icon-only controls
   have an `aria-label`. Disabled navigation is not a link.
6. **Focus ring** everywhere: 2px green base outline, offset 2px (global `:focus-visible`).
7. **Touch targets** are at least 44px on phones. Buttons are 44px by default and only
   shrink to 38px on large screens with a fine pointer.
8. **Colour is never the only signal.** Intents always show their label; meters expose their
   value; selected chips use `aria-pressed`.
9. **A person's colour comes from `personHue(userId)` only.**

## Contrast

Every allowed pairing is listed in `lib/design/pairs.ts` and checked by
`lib/design/contrast.test.ts` on every CI run:
- **text:** 4.5:1;
- **large text only:** 3:1;
- **borders, focus rings and selected states (WCAG 1.4.11):** 3:1.

The style guide shows each pair with its ratio. The axe check in
`frontend/e2e/tests/accessibility.spec.ts` checks `/design` and `/login` at desktop and phone
sizes.

**Results when the system was built (2026-10-02):**
- **Text colours:** every text colour in the brief passed 4.5:1 on every background it is
  used on, so none had to be darkened. The lowest are coral ink on coral track (5.02:1) and
  muted on coral or violet tint (5.07:1).
- **The filled badge:** with the coral base it failed (paper text, 3.71:1). It uses `#B83D28`
  instead (5.49:1).
- **The field underline:** in `line-strong` it would fail as a control boundary (1.72:1). It
  uses `muted` instead (6.04:1 on paper).
- **The selected-chip border:** in the base colour, amber would fail (2.8:1). Selected chips
  use the hue's ink instead (all at least 6.7:1).
