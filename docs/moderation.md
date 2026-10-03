# Moderation: reading and resolving reports

This page is for the project owner (the moderator). The normal way to moderate is the
**moderation page in the app**. The PowerShell steps further down (admin API with the
`X-Admin-Token`) still work as a backup.

## The moderation page (in the app)

**One-time setup:** Render → the API service → **Environment** → add `MODERATOR_EMAILS` =
the email address you sign in with (several addresses: comma-separated) → **Save, rebuild
and deploy**. It is not a secret, but keep it in Render, not in the repository.

**Using it:**

1. Sign in to the app as usual. **Settings → Account settings** shows a **Moderation** link
   (only for moderator accounts). It opens `/moderation`.
2. **Open reports**, oldest first. Each shows the reason in plain words, the reporter's
   note, and the copy the report kept, with the reported person's parts highlighted (for a
   message report, the reported message is outlined). You never see whole conversations.
3. **Resolve** (with an optional note for your records) closes a report.
4. **Suspend this account** signs the reported person out at once. They can't sign in,
   can't be messaged and aren't shown in matches. The report stays open until you resolve
   it.
5. **Suspended accounts** lists everyone suspended, with your note; **Unsuspend** lets them
   back in.
6. **Resolved reports** shows what you have closed.

Every resolve, suspend and unsuspend is written to an audit log (who, what, when, your
note; no message text), kept for a year (`MODERATION_LOG_RETENTION_DAYS`). The page and its
API allow `MODERATION_REQUESTS_PER_MINUTE` (60) requests a minute per moderator. You can't
suspend yourself or another moderator.

## What a report contains

People can report three things from the app: a **chat message** (under each message from
the other person), an **intro** they received, and a **profile** (on a match card or a
connection card). For each report the API keeps:

- what was reported (`target`: `message`, `intro` or `profile`) and its id (`target_id`);
- the reason they picked and their optional note. Reasons, as people see them:
  harassment or bullying (`harassment`), spam or advertising (`spam`), scam or asking for
  money (`scam`), sexual or inappropriate content (`inappropriate`), safety concern:
  threats, self-harm, or someone may be under 18 (`safety`), something else (`other`);
- a frozen copy of what the reporter saw (`messages`):
  - a message: it and the 10 messages before it, each marked as sent by the `reporter` or
    the `reported` person;
  - an intro: its `request` text and its `note`;
  - a profile: its `summary`, `offers`, `seeks`, `interests` and `availability`, plus
    `name` and `links` only if the two were connected;
- the two account ids and, for messages and connected profiles, the connection id. An id
  becomes empty if that account or connection is deleted; the copy stays.

The reporter is told only that the report was received. The reported person is not told.
Resolved reports are deleted 180 days after you resolve them (`REPORT_RETENTION_DAYS`).
Open reports are kept until you resolve them.

## Backup: the admin API from PowerShell

### One-time setup (Render)

The admin token goes **only** into the Render settings. Never put it in the repository,
GitHub secrets, a script, a chat message or a note file.

1. Make a token: open PowerShell and run
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Copy the output.
2. Render → the API service → **Environment** → **Add environment variable**:
   - `ADMIN_API_TOKEN` = the token you just made;
   - `MODERATOR_EMAIL` = the address that should get the alert email.
3. **Save changes**. Render redeploys the API (about two minutes).
4. Close the PowerShell window, so the token is not left on screen.

### When the alert email arrives

At most one email an hour, sent on the scheduler's hourly tick, says how many new reports
are waiting. It never contains message text, names or reasons.

1. Render → the API service → **Environment** → click the eye next to `ADMIN_API_TOKEN`
   and copy the value.
2. Open PowerShell and run these lines. Replace the address with your API's Render
   address (the `API_URL` from deployment-plan.md). Paste the token when asked; what you
   paste at the prompt is not saved in the command history.

   ```powershell
   $api = "https://YOUR-API.onrender.com"
   $headers = @{ "X-Admin-Token" = (Read-Host "Admin token") }
   $page = Invoke-RestMethod "$api/api/v1/admin/reports" -Headers $headers
   foreach ($r in $page.items) {
     "=== Report $($r.id): $($r.target), $($r.reason) ($($r.created_at))"
     "Note: $($r.details)"
     $r.messages | Format-Table label, sender, sent_at, body -Wrap
   }
   ```

   The first call can take about a minute if the API was asleep. If `next_cursor` is not
   empty, there are more: add `?cursor=<that value>` to the address and run the
   `Invoke-RestMethod` line again.
3. When you have dealt with a report, mark it resolved (the note is for your own records):

   ```powershell
   Invoke-RestMethod "$api/api/v1/admin/reports/REPORT-ID/resolve" -Method Post `
     -Headers $headers -ContentType "application/json" -Body '{"note": "Warned them."}'
   ```

4. To see resolved ones: `Invoke-RestMethod "$api/api/v1/admin/reports?status=resolved" -Headers $headers`.
5. Close the PowerShell window when you are done.

### Limits and safety of the admin API

- Every admin request is limited to `ADMIN_REQUESTS_PER_MINUTE` (30) per IP address,
  counted before the token is checked, so guessing the token is slow.
- The token is compared in constant time and the `X-Admin-Token` header is never logged.
- Without `ADMIN_API_TOKEN` the admin endpoints answer 404 (they are switched off).
- A wrong or missing token gets 403.
- People can file at most `REPORTS_PER_DAY` (5) reports a day.

## Not built yet

Automated screening of profiles and messages (to be decided; it would send text to an AI
provider, which needs consent and privacy wording).
