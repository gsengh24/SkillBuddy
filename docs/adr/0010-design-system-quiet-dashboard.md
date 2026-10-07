# 10. Design system: direction B, "Quiet dashboard"

- **Status:** Superseded by [ADR 0014](0014-design-system-cynergi.md) (2026-10-07)
- **Date:** 2026-10-02

## Context

The web app had placeholder styling (Tailwind defaults). Product screens (discover,
profile, matches) are next, so they need one shared visual language first. Desktop and
phone matter equally, and the system must meet WCAG 2.1 AA.

## Decision

Direction B, "Quiet dashboard", chosen by the owner on 2026-10-02.

- **Look:** calm, light green and white, with soft colour; thin outlined controls, never
  bulky filled buttons; no animations or transitions.
- **Colour:** six hues, each with roles for base, ink, tint, edge and track. Each intent has
  a hue, and a person's colour comes from a stable hash of their user id, never a personal
  attribute.
- **Fonts:** Manrope and IBM Plex Mono through `next/font`, self-hosted, with no runtime CDN.
- **Built as:**
  - tokens in `frontend/lib/design/tokens.ts`, mirrored as a Tailwind v4 `@theme` in
    `app/globals.css`, with the default palette removed;
  - shared components in `frontend/components/ui`;
  - the app shell in `frontend/components/shell`;
  - a development-only style guide at `/design`.
- **Specification and usage rules:** [docs/design/design-system.md](../design/design-system.md).
- **Accessibility tests:**
  - a contrast test over every allowed colour pair (text at 4.5:1, large text and control
    states at 3:1);
  - component render tests;
  - axe-core (via `@axe-core/playwright`, a new test-only dependency of the e2e package) on
    the style guide and sign-in page in CI.

## Consequences

- One source of colour values, guarded by tests. Off-palette colours can't be used by
  accident, because the default palette is gone.
- Two pairs failed contrast and changed:
  - the filled badge uses a darker coral (`#B83D28`);
  - text-field underlines use `muted`, not `line-strong`.
  
  Selected chips take their border from the hue's ink, not its base. No text colour from
  the brief had to be darkened.
- Four edge and track values were not in the brief and were derived (documented).
- Fonts are fetched from Google Fonts at **build** time, so builds need network access.
- New screens must use the components and tokens. Raw hex values in components need a new
  token.
