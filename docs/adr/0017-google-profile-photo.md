# 17. Profile pictures: the Google account picture, by choice, for connections only

- **Status:** Accepted
- **Date:** 2026-10-10
- **Amends:** [ADR 0014](0014-design-system-cynergi.md) ("Avatars ... There are no photos")
  and the storage rule "No file or image uploads" (CLAUDE.md). Builds on
  [ADR 0011](0011-google-sign-in.md) (Google sign-in). Uploads stay banned.

## Context

Avatars are initials on green or ink (ADR 0014). The owner asked on 2026-10-10 for a
profile picture option, with one hard condition: the picture must not be stored in our
database.

Three limits shape the answer:

- **Storage and cost.** The free database holds 0.5 GB and no money is spent
  ([ADR 0004](0004-zero-cost-constraint.md)). Image bytes cannot live in PostgreSQL, and a
  new object store is a new service to find, cap and watch.
- **Moderation.** Any picture a person can choose freely is something a moderator has to
  be able to review and remove. There is no tooling for that today.
- **Privacy.** A name is shown only once two people are connected. A face shown earlier
  would undo that.

A picture kept only in the person's own browser was considered and rejected: nobody else
could see it, which is the point of the feature.

## Decision

1. **The only picture is the person's Google account picture.** "Sign in with Google"
   already asks for the `profile` scope, and the ID token carries a `picture` claim: the
   address of the account picture on Google's servers. No new scope, no new service.
2. **We store the address, never the picture.** `users.google_picture_url` holds what
   Google sent at the last Google sign-in (at most 300 characters, about 100 in practice).
   The bytes stay with Google and are loaded by the viewer's browser.
3. **Only Google's picture hosts are accepted.** The claim is kept only if it is an
   `https://lh3`–`lh6.googleusercontent.com/...` address; anything else is ignored. The
   web app's Content-Security-Policy allows images from exactly those four hosts, so a
   picture can never come from anywhere else.
4. **Off by default; the person switches it on.** `PATCH /me/profile` takes
   `show_photo`. On copies the address into `profiles.photo_url`; off sets it to null.
   With no Google picture on file the switch answers `photo_unavailable` (409). There is
   no upload and no way to give an address of one's own.
5. **Connections only.** `photo_url` on a person (`PersonOut`) is set under the same rule
   as `display_name` and `links`: only once the two are connected. Match cards, pending
   intros, block lists and moderation views never carry it.
6. **It follows Google.** Every Google sign-in refreshes the stored address, and a
   profile that shows the picture follows it. If Google stops sending one, the profile
   goes back to initials.
7. **Initials stay the fallback.** The `Avatar` component draws the initials and lays the
   picture over them, so a picture that fails to load leaves the initials showing. The
   picture is requested with `referrerpolicy="no-referrer"`.
8. **The AI never sees it.** The address is not part of any prompt (ADR 0007).

## Consequences

- People who sign in only with email codes have no picture option. They can sign in with
  Google once (same address) to get one.
- A person cannot pick a different picture here; they change it in their Google account,
  and it updates at their next Google sign-in. Sessions last up to 90 days, so a change
  can take that long to show.
- When someone views a connection's picture, their browser asks Google for it, so Google
  sees that viewer's IP address and browser. The privacy policy says so. This is the one
  place the web app loads anything from another site.
- Google does not publish a quota for these addresses and does not offer them as a hosting
  service. If Google refuses or changes them, people see initials; nothing breaks
  (docs/free-tier-limits.md).
- Moderation: a report about a person already covers their picture, and a suspended or
  banned account is hidden with its picture. There is **no** moderator action to remove
  one person's picture on its own yet; that needs an owner-reviewed PR if it is wanted.
- Teams (ADR 0016) do not show pictures yet. Team members see each other's names without
  being connected, so whether they should see pictures is a separate owner decision.
- Storage: two short nullable columns, about 0.2 KB per person who shows a picture
  (docs/storage-budget.md). Both go with the account on deletion.
- The data export includes the stored address.

## Alternatives considered

- **Uploads to a free object store** (for example Supabase Storage or Cloudinary): lets
  anyone pick any picture, but adds a service, an upload path, resizing, deletion on
  account delete, and picture moderation. Rejected for now.
- **A pasted image link:** the CSP would have to allow every host, links rot, and a link
  can be used to track whoever views it. Rejected.
- **Gravatar:** derives the address from a hash of the email, which lets others test
  guesses at someone's email. Rejected.
- **Browser-only storage:** visible to nobody else. Rejected.
