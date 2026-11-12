# 23. Reading resume PDFs in the browser with PDF.js

- **Status:** Accepted
- **Date:** 2026-11-12
- **Relates to:** [ADR 0004](0004-zero-cost-constraint.md), [ADR 0020](0020-skill-suggestions.md),
  [ADR 0022](0022-chip-first-onboarding.md)

## Context

Onboarding step 2 offers "Skip the typing": import a resume PDF (screen 6) or paste text
(screen 7) and get skill chips to confirm. Storage rule 1 forbids file uploads, and resumes
are full of personal details (name, phone, email, address). The file must therefore be read
on the device, cleaned there, and never sent or kept.

## Decision

- **Library:** [PDF.js](https://github.com/mozilla/pdf.js) (`pdfjs-dist`, pinned to
  6.5.438). Apache-2.0, maintained by Mozilla, free, no account or card (ADR 0004). It only
  extracts text here; nothing is rendered.
- **Lazy-loaded on this screen only.** `lib/onboarding/pdf-text.ts` imports it with a
  dynamic `import()` when someone picks a file, so no other page carries it. Sizes, gzipped:
  about 135 KB for the library and 380 KB for its worker (465 KB and 1.2 MB minified). The
  worker is the package's own `pdf.worker.min.mjs`, bundled by Next.js and served from this
  site; it is stopped when reading ends.
- **Text only, nothing fetched:** fonts are not loaded (`disableFontFace`), no system fonts,
  no worker fetches, no XFA, at most 5 pages, files up to 2 MB. PDF.js 6 has no `eval`, so
  the CSP keeps `script-src` without `'unsafe-eval'` in production.
- **CSP change:** one directive, `worker-src 'self'`. Workers come only from this site; no
  `blob:` or `data:`. Everything else stays as strict as before.
- **On the device:** `lib/onboarding/redact.ts` removes email addresses, links, phone
  numbers (10+ digits), address lines and the name at the top first. `lib/onboarding/spot.ts`
  then finds names from the bundled skill list only (ADR 0020): the onboarding chips plus the
  hand-written list from the new `GET /api/v1/skills/common` (names only; no text goes to
  the server). No AI call.
- **Nothing saved until confirmed.** The person keeps or drops each chip; kept chips go back
  into step 2 (and interests into step 3), which saves them only when the person continues.
  The text is dropped from memory when the screen closes.

## Consequences

- Scanned (image-only) PDFs have no text; the screen says so and suggests pasting instead.
  OCR in the browser would be a much larger download and is left out.
- Spotting is plain word matching against a short list. It misses skills that aren't listed
  (people can still type them on step 2) and won't suggest projects: the "Projects" group in
  mockup 06 has nowhere to be stored yet, so it is not shown.
- A PDF.js security fix means a version bump of a pinned dependency (Dependabot).
