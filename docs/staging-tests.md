# Staging tests (by hand)

Short checks to run on the staging site after a change that CI cannot fully show. Write
the date and result at the end of each section.

## Chat ([ADR 0012](adr/0012-chat-delivery-by-polling.md))

**Before you start:** Actions → Migrate staging has run after the chat PR (migration 0009).

### Set up two test accounts (once)

1. Use two email addresses you can read, for example `you+a@gmail.com` and
   `you+b@gmail.com` (Gmail delivers both to `you@gmail.com`). Never use someone else's.
2. Open the staging site in a normal window (**A**) and a private window (**B**). Sign in
   as one address in each.
3. In both, create a profile (Discover → **Create your profile**). Give B something A will
   ask for, for example B: "I design mobile app screens"; A: "I'm building a budgeting
   app".
4. In A, on Discover, ask for "a designer for my app" → **Find matches**. When B appears,
   **Send intro**.
5. In B, open Notifications → **Accept**. Both now see each other on Messages.

### Checks

| # | Do this | You should see |
| --- | --- | --- |
| 1 | In A, Messages → **Open chat** | B's name, "No messages yet", and "Messages are deleted 90 days after they're sent." under the box |
| 2 | In A, type "Hello" → **Send** | It appears at once on A's side |
| 3 | In B, open Messages (do not open the chat) | A red badge with **1** next to A's name |
| 4 | In B, **Open chat**, then go back to Messages | "Hello" is in the chat; the badge is gone |
| 5 | With both chats open, send a reply from B | It shows in A within about 3 seconds, without reloading |
| 6 | Leave A's chat open and untouched for **11 minutes** (no typing, no messages, keep the tab in front) | A shows "Paused while it's quiet. New messages load when you come back." |
| 7 | While A is paused, send a message from B, wait a minute | It does **not** appear in A yet |
| 8 | In A, click **Check for messages** (or switch to another tab and back) | B's message appears, and the "Paused" line goes away |
| 9 | In A, switch to another browser tab for a minute, send from B, then come back to A | The message appears as soon as A is in front again |

If a check fails, note which one and what you saw, and ask Claude Code to look into it.

Result: _not run yet_

## Pair spaces ([ADR 0013](adr/0013-pair-spaces-v1.md))

**Before you start:** the two connected test accounts from the chat section (A and B).

| # | Do this | You should see |
| --- | --- | --- |
| 1 | In A, Messages → **Open pair space** (or the sidebar's **Pair spaces** on a computer) | "You and B", with empty goals, skills and notes |
| 2 | In A, add a goal "Ship the first version" with a due date | It appears with "due" and the date |
| 3 | In B, open the same space and tick that goal | It shows as done (crossed out); reload A: done there too |
| 4 | In A, add a skill "Public speaking" | It shows under "You" in A, and under A's name in B (without a Remove button) |
| 5 | In B, write a note about the goal | In A, the note shows with B's name, the time and the goal it is about |
| 6 | In A, try to remove B's note | There is no Delete on it; only on your own notes |
| 7 | In B, block A, then open the space in either window | "This page could not be found" for both |

Result: _not run yet_
