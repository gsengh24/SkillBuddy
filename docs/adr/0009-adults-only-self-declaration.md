# 9. Adults only (18+), by self-declaration

- **Status:** Accepted
- **Date:** 2026-10-02

## Context

ADR 0006 made Skill Buddy adults-only: a new account must tick "I am 18 or older"
(`age_confirmed`, stored as `users.age_confirmed_at`) as well as accept the terms.

On 2026-10-01 the owner decided to allow under-18 users. That decision was recorded as a
dated note in ADR 0007 §3a. It was proposed as an ADR numbered 0009 in PR #19, which was
**closed without merging**, so no earlier ADR 0009 exists. On 2026-10-02 the owner
reversed it. This ADR records the decision that stands.

## Decision

The platform is 18+ only. Age is a self-declaration via a required tick box; no
verification is done. Decision by the owner on 2026-10-02.

In practice:

- **Sign-up.** "I am 18 or older" sits beside the terms tick box. Both are required to
  create an account; without them, `POST /api/v1/auth/otp/verify` refuses with
  `400 consent_required` and the code stays usable.
- **What is stored.** `users.age_confirmed_at` records when the box was ticked. No date of
  birth or other age data is collected.
- **Existing accounts.** An active account with no `age_confirmed_at` must tick the box on
  its next sign-in before it can use the app. Its terms acceptance is not asked again. This
  covers any account created while the under-18 decision was being considered.
- **The API field.** `age_confirmed` keeps its shape in `/api/v1`: a boolean, default
  `false`. It must be `true` whenever an account is created or has no recorded
  confirmation. Existing confirmed users can sign in without resending it, so making it
  mandatory in the schema is not needed and would be a breaking change within `/api/v1`.
- **No restricted features.** Every user is treated the same way.

ADR 0006 is unchanged and still applies; this ADR adds the sign-in rule for unconfirmed
accounts and states the self-declaration limits explicitly.

## Consequences

**Known limits:**

- Self-declaration is not verification.
- Some students may be 17.
- Legal review of the privacy policy and terms is pending before launch.

**Other effects**

- **Groq.** This meets Groq's 18+ condition on paper (ADR 0007 §3a). The question to Groq
  support is still open.
- **Evaluation data.** The eval set keeps its 18+ requirement (ages 18–100).
