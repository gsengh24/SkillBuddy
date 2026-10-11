# ADR 0017: Dark-only theme

Status: accepted (owner request, 2026-10-12). Amends [ADR 0014](0014-design-system-cynergi.md).

## Decision

The app is always dark, whatever the visitor's system setting. The dark palette added with the
Home redesign (`app/globals.css`) is now the only one: it replaces the light values on `:root`,
and the `prefers-color-scheme` media query and `data-theme` selectors are gone. There is no
switch. `color-scheme` is `dark` and the browser theme colour is the dark page background.

Legacy hues (`components/ui`: amber, coral, blue, violet, teal) and the notification badge got
dark values too (dark tints, light inks); with light inks on the old pale tints the style guide
failed the contrast check. `lib/design/tokens.ts` and `app/globals.css` now hold only the dark
palette, and the contrast and sync tests check exactly what visitors see.

## Not covered

The static landing page (`public/landing/index.html`) keeps its own design and is not changed.
