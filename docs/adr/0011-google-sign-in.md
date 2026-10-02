# 11. Sign in with Google for @thapar.edu, with email codes as the fallback

- **Status:** Proposed (awaiting the owner's merge; it touches sign-in)
- **Date:** 2026-10-02
- **Amends:** [ADR 0006](0006-authentication-and-sessions.md) (authentication and sessions)

## Context

ADR 0006 chose passwordless email codes as the only way to sign in, and left Google as a
later identity (`auth_identities.provider = 'google'` already exists for it). Two things
make Google worth adding now:

- **Email delivery is the weak point.** Codes go through one Gmail account with a 450 a day
  cap (ADR 0008), and delivery to `@thapar.edu` still has to be proven (pre-launch
  checklist item 8). A Google sign-in needs no email at all.
- **The audience is one college.** thapar.edu mail runs on Google Workspace (its MX
  records point to `aspmx.l.google.com`, checked 2026-10-02), so every student already has
  a Google account for their college address, and Google can say which domain manages it.

Also, until now any email address could sign in. The owner decided (2026-10-02) to add
an allow-list, an exception list and a block list, and to enforce them on **both** methods.

## Decision

### Methods

- **Google** (OpenID Connect) is the first option on the sign-in page; **email codes** stay
  below it and keep working exactly as before for everyone allowed in.
- Google is off unless `GOOGLE_SIGNIN_ENABLED=true` and the client id, client secret,
  redirect URI and at least one allowed domain are all set. Otherwise the button is hidden,
  `GET /api/v1/auth/methods` reports `google: false` and the Google endpoints answer 404.

### Who may sign in (`app/services/auth/policy.py`)

| Setting | Email codes | Google |
| --- | --- | --- |
| `ALLOWED_EMAIL_DOMAINS` (e.g. `thapar.edu`) | Allowed | Allowed; the **only** way in |
| `ALLOWED_EMAILS` (exceptions, e.g. the owner's Gmail) | Allowed | Not allowed (owner's decision) |
| `BLOCKED_EMAILS` | Refused | Refused |
| All lists empty | Anyone (as before) | Google unavailable |

Matching is exact and case-insensitive on the address, or on the part after its last
`@`: `thapar.edu` admits neither `evilthapar.edu`, `thapar.edu.example.com` nor
`mail.thapar.edu`. Refusals return `403 email_not_allowed`, the same for an outside domain
and a blocked address, and are written to the audit log.

### The Google flow

Authorization-code flow with PKCE (S256), run on the server. Scopes: `openid email
profile` only.

1. `POST /api/v1/auth/google/start` with the two tick-box answers and an optional `next`
   path (same-site paths only). The server stores an `oauth_states` row (an HMAC of a
   random `state`, the answers, `next`, 10-minute expiry) and sets an httpOnly, SameSite=Lax
   cookie holding the `state`, scoped to `/api/v1/auth/google`. The nonce and the PKCE
   verifier are derived from the state with the server's secret key, so neither is stored.
   It returns Google's URL, with `hd=<domain>` as a hint for the account chooser.
2. Google redirects the browser to `GOOGLE_OAUTH_REDIRECT_URI`, which is the **web app's**
   `/api/v1/auth/google/callback`, forwarded to the API like every other call, so the
   session cookie is first-party as before.
3. The callback refuses unless the `state` matches the cookie (no login CSRF) and an
   unexpired row exists; the row is deleted at once (single use, so a replay fails).
4. The code is exchanged with the PKCE verifier and the client secret. The ID token must
   pass every check:
   - an RS256 signature from Google's key set (cached for an hour, refetched once for an
     unknown key id);
   - the issuer, the audience (our client id), expiry and issued-at (60 seconds leeway);
   - the nonce of this attempt;
   - `email_verified` is exactly `true`;
   - the `hd` claim equals the email's own domain.
5. The email must then pass the allow and block lists for Google. `hd` is never trusted
   alone: an `hd` of `thapar.edu` on a `@gmail.com` address fails step 4, and an allowed
   `hd` still needs the domain on `ALLOWED_EMAIL_DOMAINS`.
6. Sign-in then follows the email-code path exactly. That includes:
   - the 18+ and terms tick boxes for a new account, or for one without a recorded age
     confirmation (ADR 0009);
   - the storage pause on new sign-ups, and the refusals for suspended accounts and those
     pending deletion;
   - the same session, CSRF cookie and audit events (with `detail.method = "google"`).

   An existing account with the same email (made with codes) is signed in to, and the
   Google identity is linked to it. Later sign-ins find it by Google's stable `sub`.
7. The browser is redirected to `next` on success, or to `/login?error=<code>` on any
   failure. The codes are stable: `google_state_invalid`, `google_cancelled`,
   `google_failed`, `email_not_allowed`, `consent_required`, `account_pending_deletion`,
   `account_suspended`, `signups_paused`, `rate_limited`. The specific reason (for example
   `wrong_audience` or `nonce_mismatch`) goes only to the audit log and logs.

**Limits:** starts and callbacks are rate-limited per IP in PostgreSQL
(`GOOGLE_SIGNIN_LIMIT_PER_IP`, per `RATE_LIMIT_WINDOW_SECONDS`).

**Secrets:** the client secret, authorization codes, tokens and `state` values are never
logged, stored in plain form or put in an error message or redirect.

**Retention:** unused `oauth_states` rows are purged daily by `purge_auth_data` once
expired; used ones are deleted on use.

### Testing without Google

`backend/tests/fake_oidc.py` is a small OIDC provider:
- an authorize page that signs in any typed email;
- a token endpoint that checks the secret, redirect URI and PKCE;
- a JWKS endpoint;
- tamper hooks for negative tests.

How it is used:
- Unit and integration tests run it in-process.
- The dev and CI compose stack runs it as the `fake-oidc` service, and the Playwright e2e
  test signs in through it.
- The `GOOGLE_OIDC_*` endpoint overrides that point at it are refused in staging and
  production.
- It is not in the production image.

### Dependencies and design exceptions

- **PyJWT with `cryptography`** (`pyjwt[crypto]`), a widely used library, verifies the
  RS256 signature and the standard claims. No Google SDK is used.
- **The Google "G" mark keeps its four brand colours.** Google's sign-in branding rules
  require the standard logo. This is the one exception to the design system's token-only
  colours (ADR 0010). The button itself is the design system's thin outline pill reading
  "Continue with Google".

### API shape (frontend-agnostic)

`GET /api/v1/auth/methods` lets any client discover the available methods. The callback
is a browser redirect by nature. A future mobile app would use Google's native sign-in
and send the ID token to a new endpoint, reusing the same verification and policy; that
needs its own decision.

## Consequences

- Students can sign in without waiting for an email, and email codes remain for anyone
  whose Google sign-in fails, or for the owner's exception addresses.
- **Setting `ALLOWED_EMAIL_DOMAINS` makes the platform campus-only for both methods.**
  People already signed in keep their sessions, but outside addresses can no longer sign
  in again.
- The owner must create a Google OAuth client (free, no card). The steps are in
  [deployment-plan.md](../deployment-plan.md#step-6b-google-sign-in-oauth-client).
- **Thapar's Workspace admins could block the app.** Workspace lets admins restrict
  third-party apps, so a real `@thapar.edu` account must be tested early (pre-launch
  checklist). Email codes keep working if Google is blocked.
- Google could change its endpoints or keys. Key rotation is handled; endpoint changes would
  need a settings change.
