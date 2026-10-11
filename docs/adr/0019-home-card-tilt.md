# 19. Hover tilt on Home cards

- **Status:** Accepted
- **Date:** 2026-10-12
- **Amends:** [ADR 0014](0014-design-system-cynergi.md) (motion, design spec section 5)

## Context

ADR 0014 limits motion to the list in design spec section 5: fade-ups, the button lift and
press, row borders, the accordion. The owner asked for the three summary cards (Requests,
Messages, Connections) and the pair-spaces band under the Home composer to tilt toward the
pointer on hover, as in a reference recording. That is not in section 5, so it needs a
decision of its own.

## Decision

- **What moves.** Only the hovered card, and only with a mouse. It pops toward you and tilts
  in 3D toward the pointer, then eases back flat. Its neighbours stay still. The band's image
  shifts up to 4px against the tilt for depth.
- **Limits.**
  - Summary cards: scale 1.04, tilt at most 6°. Band: scale 1.03, tilt at most 4°. Both lift
    2px, inside `perspective(700px)`.
  - Ease in over 200ms, back to flat over 380ms, both ease-out, no bounce.
  - `transform` only (no shadow, filter or position). `will-change: transform` only while hovered.
  - Only with `(hover: hover) and (pointer: fine)`. Nothing on touch screens.
  - With `prefers-reduced-motion: reduce` there is no tilt and no scale, and no listener is
    attached.
  - Cards stay non-interactive. Keyboard focus never tilts anything.
- **How.** One small client component, `components/ds/tilt.tsx`: `pointermove` throttled
  with `requestAnimationFrame` writes `--rx`, `--ry`, `--s` (and friends) on the element; the
  transform lives in CSS. No animation library.

## Why

The owner asked for it. It stays inside the existing motion principles (transform only, off
for reduced motion, nothing continuous) and adds no dependency.

## Consequences

- Design spec section 5 and the motion rule in CLAUDE.md point here.
- Any other card that should tilt needs this ADR amended, not a copy of the effect.
