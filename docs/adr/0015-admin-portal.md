# 15. Admin portal: roles, two-step login, audit log

- **Status:** Accepted
- **Date:** 2026-10-08

## Context

The owner wants an admin portal (design spec section 14,
[reference-admin.html](../design/reference-admin.html)). Until now there were only:
- **The moderation page:** people listed in `MODERATOR_EMAILS`.
- **Machine endpoints under `/api/v1/admin`:** protected by `ADMIN_API_TOKEN`. One is the
  scheduler's `/admin/jobs/tick`, called by a Cloudflare Worker.

The portal will see personal data and change accounts, so access must be explicit,
strong and recorded.

## Decision

- **Roles:** `owner`, `admin`, `moderator` and `readonly`, one per admin.
  - Owners come only from the environment variable `ADMIN_OWNER_EMAILS`, so no email
    lives in the repository.
  - The other roles are rows in `admin_accounts`, given and removed by an owner.
  - With `ADMIN_OWNER_EMAILS` empty, nobody is an admin.
- **Permissions, not role names:** the code checks named permissions. The permission
  table in the reference is the contract:

  | Permission | Owner | Admin | Moderator | Read-only |
  | --- | :-: | :-: | :-: | :-: |
  | View dashboards, view users | yes | yes | yes | yes |
  | Suspend or ban users, handle reports, read messages attached to reports | yes | yes | yes | no |
  | Signup and invites, settings and switches, AI and matching, delete users and data | yes | yes | no | no |
  | Manage admins | yes | no | no | no |

- **One shared dependency:** `require_admin(permission)` guards every route under
  `/api/v1/admin`.
  - No session gets 401. A signed-in person who is not an admin gets 403.
  - An admin who hasn't finished the second step gets 401 `admin_two_step_required`.
  - An admin without the permission gets 403.
  - A test lists every route under `/api/v1/admin` and checks this for each, so a new
    route can't be left open.
  - The scheduler and operator endpoints also accept `ADMIN_API_TOKEN` (or the tick
    token). That way the Cloudflare Worker keeps working, and the same 401 and 403
    rules hold for people.
- **Two-step login (TOTP):**
  - Admins only. It uses [pyotp](https://pypi.org/project/pyotp/), MIT licensed and
    pure Python, with no other dependencies.
  - The secret is encrypted at rest with a key derived from `SECRET_KEY` (Fernet, from
    `cryptography`, already installed through `pyjwt[crypto]`).
  - A used time step can't be replayed.
  - Ten single-use recovery codes are shown once and stored as hashes.
  - Setup shows the key and an `otpauth://` link, with no QR library.
- **Admin session:**
  - Separate from the normal session: its own cookie and table, valid only after the
    second step.
  - It expires after **30 minutes without use** and at most 12 hours after it started.
  - It also needs the person's normal session, so signing out ends both.
  - A normal user never sees any of this.
- **Audit log (`admin_audit_log`):**
  - Each entry records the admin, their role, the action, the target, a reason (at least
    10 characters for every change), the time and the IP address.
  - It's written by one helper, in the same transaction as the action. If the entry
    can't be written, the action fails.
  - **A database trigger refuses `UPDATE` and `DELETE`**, so entries can't be edited or
    removed. The actor is stored without a foreign key, so deleting a person's account
    never has to change the log.
  - It grows by about 1 KB per admin action and is kept with no retention limit
    (`docs/storage-budget.md`).
- **Admin never reads message text:**
  - Admin code never reads, returns, counts by content or logs chat message bodies.
  - Counts such as messages per day are allowed.
  - A report shows only the messages the reporter attached to it.
  - User-written text is returned as plain data and shown as plain text.
- **No secrets or personal data in logs:** emails, tokens, message text and reasons are
  never written to application logs.
- **The web portal** lives at `/admin`, with its own layout, `noindex`, not in the
  sitemap and not linked from the public app.

## Consequences

- **The owner sets `ADMIN_OWNER_EMAILS` on Render.** Until then the portal is closed to
  everyone.
- **New dependency:** pyotp.
- **Losing the authenticator:** the person uses a recovery code. With none left, an owner
  removes and re-adds them (or, for an owner, someone with database access clears their
  two-step row).
- **`MODERATOR_EMAILS` and the moderation page stay** until the reports page (A3)
  replaces them.
