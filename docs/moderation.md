# Moderation: reading and resolving reports

Until the moderation page arrives with roadmap item 7, reports are read through the admin
API from your laptop. This page is for the project owner (the moderator).

## What a report contains

When someone reports a message in chat, the API keeps:

- the reason they picked (harassment, spam, scam, inappropriate, safety, other) and their
  optional note;
- a frozen copy of the reported message and the 10 messages before it, each marked as
  sent by the `reporter` or the `reported` person;
- the two account ids and the connection id. An id becomes empty if that account or
  connection is deleted; the copy of the messages stays.

The reporter is told only that the report was received. The reported person is not told.
Resolved reports are deleted 180 days after you resolve them (`REPORT_RETENTION_DAYS`).
Open reports are kept until you resolve them.

## One-time setup (Render)

The admin token goes **only** into the Render settings. Never put it in the repository,
GitHub secrets, a script, a chat message or a note file.

1. Make a token: open PowerShell and run
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Copy the output.
2. Render → the API service → **Environment** → **Add environment variable**:
   - `ADMIN_API_TOKEN` = the token you just made;
   - `MODERATOR_EMAIL` = the address that should get the alert email.
3. **Save changes**. Render redeploys the API (about two minutes).
4. Close the PowerShell window, so the token is not left on screen.

## When the alert email arrives

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
     "=== Report $($r.id): $($r.reason) ($($r.created_at))"
     "Note: $($r.details)"
     $r.messages | Format-Table sender, sent_at, body -Wrap
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

## Limits and safety of the admin API

- Every admin request is limited to `ADMIN_REQUESTS_PER_MINUTE` (30) per IP address,
  counted before the token is checked, so guessing the token is slow.
- The token is compared in constant time and the `X-Admin-Token` header is never logged.
- Without `ADMIN_API_TOKEN` the admin endpoints answer 404 (they are switched off).
- A wrong or missing token gets 403.
- People can file at most `REPORTS_PER_DAY` (5) reports a day.

## What the API cannot do yet (item 7)

Blocking, suspending an account, a moderation page in the app, and automated screening
are part of roadmap item 7. Until then, to stop someone you can set their account to
`suspended` in the database (Neon → SQL editor). That ends their sessions at once, so
they can't send anything, and others can't message them. Ask Claude Code for the exact
statement when you need it.
