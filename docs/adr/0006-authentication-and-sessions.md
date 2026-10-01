# 6. Passwordless email codes, server-side sessions, CSRF protection

- **Status:** Accepted
- **Date:** 2026-10-01

## Context

Profiles will hold personal free text, so the product needs sign-in, consent capture,
abuse controls and account deletion before Phase 1 (Phase 0 exit report, criterion 5).
Constraints: zero cost (ADR 0004), a web app now and possibly a mobile app later
(CLAUDE.md, "API design"), adults only, and no password database to protect.

## Decision

**Sign-in: one-time email codes, no passwords.**
- `POST /api/v1/auth/otp/request` sends a 6-digit code that is valid for 10 minutes. The
  response is identical whether or not an account exists, and no account lookup happens on
  this path (so timing does not differ either). A new request deletes earlier unused codes
  for that address.
- Codes are stored only as `HMAC-SHA256(key_otp, email + ":" + code)`. The key is derived
  from `SECRET_KEY` per purpose, so code, email and CSRF digests cannot be swapped.
- `POST /api/v1/auth/otp/verify` compares in constant time, allows 5 wrong guesses per code,
  and is single use (row lock plus `consumed_at`). The first successful sign-in creates the
  account and requires `age_confirmed` (18+) and `accept_terms`; it records
  `age_confirmed_at`, `terms_accepted_at` and `terms_version`. Without consent the code stays
  usable, so the person can tick the boxes and resubmit.
- Codes are emailed by the Arq worker, not inline. The job expires with the code and keeps
  no result, so the code does not linger in Valkey.
- Sign-in methods live in `auth_identities (provider, subject)`, unique per provider and
  subject. Google sign-in later becomes another provider; it is not built now.

**Sessions: opaque token, stored hashed, in an httpOnly cookie.** No JWTs and nothing in
`localStorage`.
- A random 256-bit token goes in the `session` cookie: `HttpOnly`, `Secure` (except on the
  plain-http local stack; refused in staging and production), `SameSite=Lax`, `Path=/`.
- The database stores only `SHA-256(token)`, plus user agent and IP (truncated).
- Expiry: 30 days sliding (refreshed at most hourly, to limit writes) and 90 days absolute.
  The cookie lives until the absolute limit; the server enforces both.
- Logout deletes the session row; logout-all deletes all of the user's sessions.
- Non-browser clients may send the same token as `Authorization: Bearer <token>`.

**CSRF: signed double-submit token.** Chosen over a "required custom header" because it
does not depend on CORS configuration staying correct.
- On sign-in, the API sets a `csrf_token` cookie (not httpOnly, same flags otherwise) whose
  value is `HMAC(key_csrf, session_token_hash)`.
- Every state-changing request (anything other than GET, HEAD, OPTIONS) authenticated by
  the session cookie must send it back in `X-CSRF-Token`; mismatches get
  `403 csrf_failed`. Being bound to the session, a token from another session is useless.
- `GET /auth/me` re-issues the cookie so a client can recover it.
- Bearer-authenticated requests are exempt: browsers never attach bearer tokens on their
  own.
- The unauthenticated OTP endpoints require `Content-Type: application/json` (415
  otherwise). Cross-site HTML forms therefore cannot reach them, and other cross-site
  requests need a CORS preflight that our CORS allow-list rejects.

**Rate limits in Valkey** (fixed windows; settings `OTP_*_LIMIT_*`,
`RATE_LIMIT_WINDOW_SECONDS`).
- Per IP and per email: code requests 10/IP and 3/email per 10 minutes; verifications 30/IP
  and 10/email per 10 minutes.
- Over the limit: `429 rate_limited` with `Retry-After`.
- Email keys use the email's HMAC, never the address.
- If Valkey is unreachable the endpoints fail closed with `503`.

**Account deletion.**
- `DELETE /api/v1/me` sets `status = pending_deletion`, `deleted_at`, and
  `deletion_scheduled_for = now + 30 days`, and revokes all sessions.
- Sign-in is refused during the grace period with `403 account_pending_deletion`, naming
  the date.
- A scheduled job hard-deletes the account after the grace period; `ON DELETE CASCADE`
  removes identities, sessions and audit events.

**Audit log.** `auth_events` is append-only: a database trigger rejects UPDATE. It records
event type, user, email HMAC, IP and truncated user agent; never codes, tokens or addresses.

**Logging.** Codes and tokens are never logged; emails only as `a***@domain`.

**Retention** (storage rules):
- `otp_codes` purged once expired;
- `sessions` purged once expired (90 days at most);
- `auth_events` pruned after a fixed number of days;
- users and all their rows hard-deleted after the grace period.

The retention and deletion jobs run on the Arq worker (added with email sending).

## Consequences

- No passwords to store, reset or leak; sign-in depends on email delivery working.
- Sessions can be revoked instantly (logout, logout-all, deletion), unlike JWTs.
- Every authenticated request costs one indexed lookup; sliding updates are at most hourly.
- The web client must read the CSRF cookie and send `X-CSRF-Token` on writes.
- Valkey is now on the sign-in path: if it is down, nobody can request or verify codes.
- Adding Google sign-in later needs an OAuth flow and a new identity row, not a schema
  rewrite.
