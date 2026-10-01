# 9. Minors are permitted; no age requirement

- **Status:** Accepted
- **Date:** 2026-10-01
- **Supersedes:** [ADR 0006](0006-authentication-and-sessions.md)

## Context

ADR 0006 made Skill Buddy adults-only. A new account had to confirm it was 18 or older
(`age_confirmed`, recorded in `users.age_confirmed_at`) as well as accept the terms.
ARCHITECTURE.md §8 had an "Age gate: adults only at launch (18+)".

Skill Buddy launches on a single college campus, where some students are under 18. The
owner wants them to be able to join on the same footing as everyone else.

## Decision

Minors are permitted, with no parental-consent flow and no age-based restrictions.
Decision by the owner on 2026-10-01.

In practice:

- **Sign-up asks only for terms acceptance.** There is no age question, age checkbox or
  date of birth anywhere in the API or the UI, and no age is collected or stored.
- **API compatibility.** `POST /api/v1/auth/otp/verify` still accepts the old
  `age_confirmed` field, now marked deprecated and ignored, so clients that send it are not
  rejected. This keeps the change non-breaking within `/api/v1`. The web app no longer
  sends it.
- **Database.** `users.age_confirmed_at` stays in place, nullable and unused, so no
  migration is needed. New accounts leave it empty.
- **No restricted features.** Every user has the same features, limits and matching.
- **The rest of ADR 0006 still applies:** email codes, sessions, CSRF protection, rate
  limits, the audit log and account deletion. ADR 0001 lets a superseded ADR change only its
  status line, so those decisions are not repeated here; read ADR 0006 for them.

## Consequences

**Known risk:** DPDP Act obligations for children's data. India's Digital Personal Data
Protection Act 2023 treats anyone under 18 as a child and sets specific obligations for
processing children's personal data. This design does not implement them. Legal review of
the privacy policy and terms is pending before launch.

**Other effects**

- **Groq.** ADR 0007 §3a's 18+ condition for Groq may not be satisfied. The open question
  for Groq support and the Cloudflare-only and template-only fallbacks are recorded there.
- **Matching across ages.** Minors and adults can be matched with each other. Contact still
  needs two-sided consent, and the planned safety controls in ARCHITECTURE.md §8 (screening,
  block and report, rate limits) apply to everyone.
- **Simpler sign-up.** The form has one checkbox (terms) instead of two.
- **Evaluation data.** The eval set no longer requires profiles to be 18 or over; the age
  field keeps only a plausibility range.
