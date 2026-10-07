# 14. Design system: Cynergi

- **Status:** Accepted
- **Date:** 2026-10-07
- **Replaces:** [ADR 0010](0010-design-system-quiet-dashboard.md) ("Quiet dashboard")

## Context

The owner chose a new look and a new name, Cynergi, on 2026-10-07. The contract is
[docs/design/design-spec.md](../design/design-spec.md). Two reference pages,
[reference-landing.html](../design/reference-landing.html) and
[reference-home.html](../design/reference-home.html), decide how things look; the spec
decides behaviour, accessibility and constraints.

ADR 0010 conflicts with the spec in three ways. It bans all motion, allows outline buttons
only, and colours people with six hues. The redesign lands one PR at a time, so old and new
screens live side by side for a while.

## Decision

- **Look:** light theme with a white page, near-black ink and one brand green. The page
  uses hairline borders, bold tight headlines and generous space.
- **Colour:**
  - The palette is spec section 2: `bg`, `panel`, `line`, `ink`, `green`, `green-tint`,
    `mint`, `danger` and the rest.
  - The values live in `frontend/lib/design/tokens.ts` (`colors`), and on `:root` in
    `app/globals.css` under the spec's names (`--bg`, `--panel`, and so on).
  - They are mapped into the Tailwind theme, with Tailwind's default palette removed.
  - Components use tokens only, never raw hex.
- **Buttons:**
  - Variants: primary (solid ink, white text, at most one per view), outline (green),
    ghost, white (on the green band) and danger.
  - Every button is 44px high on touch screens. With a mouse, buttons are 40px (default)
    or 36px (compact).
- **Avatars:** initials in white on green or ink. The fill comes from `avatarFill(userId)`,
  a stable hash of the id and nothing else. There are no photos.
- **Motion:**
  - Allowed only as described in spec section 5, using `transform` and `opacity`.
  - Sections fade up once as they enter the viewport (one shared `useInView` hook), hero
    cells fade up 70ms apart, and buttons lift 2px on hover and press to 97%.
  - The accordion's height animation is the one spec-approved exception.
  - `prefers-reduced-motion: reduce` turns all of it off.
- **Fonts:** Inter (body), Inter Tight 800 (display) and JetBrains Mono (labels). They load
  through `next/font`, Latin subset only, are self-hosted and make no runtime request
  (the CSP is unchanged).
- **Components:**
  - New and restyled screens use `frontend/components/ds`.
  - The older `frontend/components/ui` stays until every screen has moved over. Its
    neutrals and greens already point at the new palette, so existing screens pick up the
    new look without a redesign.
- **Brand:** `lib/brand.ts` holds the new name (`displayName` "Cynergi", `wordmark`
  "cynergi"). Pages keep showing the old name until the owner-reviewed rename PRs. The new
  logo is one component (`components/ds/logo.tsx`) with a placeholder four-dot mark until a
  vector logo arrives.
- **Style guide:** `/design` is shown in development and on Vercel preview deployments
  (`isStyleGuideEnabled()` in `lib/env.ts`, which reads `VERCEL_ENV`), and answers 404 in
  production. It is never indexed.

### Accessibility over the reference

Where the spec's colours or the reference pages fall below WCAG AA, accessibility wins
(spec section 8). The contrast test enforces the same minimum ratios as before: 4.5:1 for
text, 3:1 for large text and for control edges and states.

| Spec or reference | What we use | Why |
| --- | --- | --- |
| `--muted` `#6B6F6A` | `#696D68` (two steps darker) | The spec value is 4.44:1 on green tint |
| Field border `--line` | `--muted-2` | A field's only edge needs 3:1; `line` is 1.26:1 |
| Numbered rows: rest in `--muted-2` | `--muted` | It is normal-size text, and `muted-2` is 3.30:1 |
| Two-tone headline on green tint: rest in `--muted-2` | `--muted` | `muted-2` is 2.86:1 there, under 3:1 even for large text |
| Counters, times, placeholders in `--muted-2` | `--muted` | Small text needs 4.5:1 |
| Section numerals in `--faint` | Drawn with CSS (`::before`) | Decorative; the list itself gives the numbering |
| Button height 40px on phones | 44px on touch screens | Touch targets (spec section 7) |

To keep the older screens passing, the coral, blue, violet and teal tints are a little
lighter, so muted text still reaches 4.5:1 on them.

## Consequences

- One palette, guarded by tests:
  - every allowed pair meets its minimum;
  - restricted colours (muted-2, faint, mint, line) are checked to fail where they aren't
    allowed;
  - `:root`, the Tailwind theme and `tokens.ts` must agree.
- Two component sets coexist until the redesign PRs finish. Then `components/ui`, the six
  hues and `personHue` can go, and that change needs no new ADR.
- Pages preload about 26 KB more font data (Inter as a variable font, plus Inter Tight 800).
- The reference pages' small grey text was lighter than AA allows, so the built pages are
  a shade darker in those places.
