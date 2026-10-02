# 12. Chat messages are delivered by client polling, not WebSockets

- **Status:** Accepted
- **Date:** 2026-10-03
- **Amends:** [ARCHITECTURE.md](../ARCHITECTURE.md) §5 (data model), §6 (modules and core
  API) and §9 (technology choices), which planned "real-time chat over WebSocket" with
  "Redis pub/sub"

## Context

Chat is the next roadmap item (Phase 3 in ARCHITECTURE.md §11): two connected people
exchange text messages. ARCHITECTURE.md was written before the zero-cost decisions and
assumes WebSockets in FastAPI with Redis pub/sub to fan messages out between processes.
Three later decisions change the ground under that plan:

- **No Redis** ([ADR 0008](0008-free-runtime-jobs-and-email.md)). PostgreSQL holds the
  job queue and the rate-limit counters; there is no pub/sub service.
- **Free hosts that sleep** ([ADR 0003](0003-hosting.md), ADR 0008). The API runs on
  Render Free and the web app on Vercel Hobby. The browser reaches the API only through
  the web app's same-origin forwarder (`app/api/v1/[...path]/`), which is why the session
  cookie is first-party and CSRF works the way ADR 0006 describes.
- **Neon compute is the binding limit** (ADR 0008, "The Neon compute budget is the binding
  limit"). 100 CU-hours a month at 0.25 CU is about 13 active hours a day. Anything that
  keeps the database awake while nobody is using the app can suspend it for the rest of
  the month.

The API must also stay usable by a future mobile app (CLAUDE.md, "API design").

## Facts that shape the decision (checked 2026-10-03)

| Fact | Source |
| --- | --- |
| **Render Free:** 512 MB, sleeps after 15 minutes without inbound traffic, about a minute to wake. WebSockets are supported, and "both HTTP requests and WebSocket messages from existing connections" count as inbound traffic. The docs do not say what happens to open connections at spin-down or redeploy. | <https://render.com/docs/free> |
| **Vercel WebSockets:** in **public beta**. A connection is pinned to one function instance and is billed as function usage "while the connection is active"; connections close at the function's maximum duration, **300 s on Hobby**. Next.js has no stable upgrade API (`experimental_upgradeWebSocket()`). Messages between instances need "an external data store", Vercel suggests Redis. | <https://vercel.com/docs/functions/websockets>, <https://vercel.com/docs/plans/hobby> |
| **Vercel Hobby, per month:** 1,000,000 function invocations; 1,000,000 CDN requests; 4 active CPU-hours; 360 GB-hours of provisioned memory. Over a limit pauses the feature for about 30 days. | <https://vercel.com/docs/plans/hobby> |
| **Neon Free:** 100 CU-hours a month, scale to zero after 5 minutes idle; out of CU-hours suspends the database until the next month. Whether idle pooled connections block scale to zero is still unverified (ADR 0008, "Not verified"). | ADR 0008; [deployment-plan.md](../deployment-plan.md) |
| **Storage:** messages are budgeted at about 30 KB per user (100 retained messages × ~300 B) in [storage-budget.md](../storage-budget.md). Polling or push does not change this; retention does. | storage-budget.md |

## Options evaluated

### A. WebSockets from the browser to Vercel (rejected)

- Beta, and Next.js support is experimental.
- Every open chat tab holds a function instance busy. At the 2 GB default instance size,
  360 GB-hours is about 180 instance-hours a month (6 a day) for the whole app.
- Connections drop every 5 minutes on Hobby, so clients need reconnect and catch-up logic
  anyway.
- Fan-out between instances needs Redis, which ADR 0008 removed.
- The socket handler would live in Next.js, putting chat logic in the web app that a
  mobile client would have to duplicate.

### B. WebSockets from the browser straight to the API on Render (rejected for now)

- The browser would talk to Render's domain directly, so the first-party session cookie
  is not sent. That needs a new authentication path (a short-lived connection ticket, an
  origin check and CORS), which is new security surface beside ADR 0006.
- Fan-out works in memory only while there is one API process. More than one needs
  pub/sub: Redis (removed) or PostgreSQL `LISTEN/NOTIFY`, which holds a dedicated
  connection open all the time and may keep Neon from scaling to zero (186 CU-hours a month
  if it never sleeps, 186% of the quota; ADR 0008).
- Sockets drop on every Render redeploy and spin-down, so a catch-up REST endpoint is
  needed anyway.
- In its favour: an idle socket costs no database time, and Render counts socket traffic
  as activity, so the API stays awake during a chat.

### C. Server-sent events (rejected for now)

Same problems as A or B: a stream held open through Vercel is billed for its duration and
cut at 300 s, and a stream straight to Render needs the same new authentication as B.

### D. Client polling over the existing REST API (chosen)

- Works through the same-origin forwarder with the existing cookie, CSRF and bearer-token
  rules. No new authentication path, no new service.
- No pub/sub: every message is a row in PostgreSQL, and a poll is one indexed query for
  rows after a cursor.
- Survives sleep, redeploys and restarts with no reconnect logic: the next poll catches up.
- The same endpoints serve a future mobile app; push can be added later as an optional
  "something changed, fetch now" signal on top, without changing them.
- Costs: latency of a few seconds, and every poll is a Vercel invocation and a database
  query. Both are bounded below.

## Decision

Chat uses **REST endpoints and adaptive client polling**. There are no WebSockets, no SSE
and no pub/sub. The exact endpoint paths, the data model and the limits' values come with
the chat PR; this ADR fixes the shape and the budget.

1. **Messages are rows in PostgreSQL.** Sending is a normal `POST`. Reading is
   cursor-paginated: "messages in this conversation after cursor X", and one "what changed
   in my conversations after cursor Y" call so a client needs a single poll, not one per
   conversation.
2. **Adaptive cadence, set by the client and documented in the OpenAPI description:**
   - every **3 s** for 60 s after a message is sent or received in the open conversation;
   - every **10 s** until 5 minutes without a message;
   - every **30 s** until 10 minutes without a message;
   - then **stop**, and resume on focus, typing or a tap.
   - **No polling while the tab is hidden**, and none outside the Messages pages: elsewhere
     the unread dot updates on page load, as now.
3. **Hard caps** (CLAUDE.md, zero-cost rule 5), as settings:
   - a per-user rate limit on the poll endpoint, using the existing PostgreSQL rate
     limiter;
   - a global daily poll budget.

   When a cap is hit, the API answers `429` with `Retry-After`, and the client falls back
   to one poll a minute. Chat slows down; it does not stop, and Vercel is never pushed to
   its 30-day pause.
4. **Budget.** Half of Vercel's 1,000,000 monthly invocations and CDN requests is
   reserved for chat polls: about **16,000 a day**. An active conversation polls about 300
   times an hour on this cadence (at most 1,200), so the budget covers about **50
   active chat-hours a day**, about 10 minutes per person per day at 300 daily active
   users. The global daily cap is set from this number.
5. **Neon.** A poll keeps the database awake only while someone is actually chatting. The
   10-minute stop means a forgotten tab adds at most 10 minutes of awake time, not a month
   (a tab polling every 30 s forever would keep Neon awake around the clock).

## What changes in ARCHITECTURE.md (in this PR)

| Section | Before | After |
| --- | --- | --- |
| §5 data model, `conversations / messages` row | "Real-time chat; retained per privacy policy" | "Chat, delivered by polling (ADR 0012); retained per privacy policy" |
| §6 modules, Messaging | "Real-time chat over WebSocket, read state, history" | "Chat over REST with adaptive client polling (ADR 0012), read state, history" |
| §6 core API | "GET /connections, WS /chat — Connections list and real-time chat" | "GET /connections, GET/POST conversation messages — Connections list and chat, polled (ADR 0012)" |
| §9 technology choices, chat row | "Real-time chat — WebSockets in FastAPI, Redis pub/sub — Enough for early scale — Managed service such as Ably" | "Chat — REST and adaptive client polling, PostgreSQL only (ADR 0012) — Works on sleeping free hosts with no pub/sub service — WebSockets or SSE, or a managed service such as Ably, once hosting is always-on" |
| §11 Phase 3 deliverables | "Real-time chat" | "Chat (polled, ADR 0012)" |

Out of scope: other ARCHITECTURE.md lines still mention Redis (§4, §5 and §9: queue, cache
and rate limits). ADR 0008 superseded them; tidying them is a separate docs change.

## Consequences

**Positive**

- Zero cost and no new service, dependency or authentication path.
- Works the same in dev, CI (Playwright can test it) and on sleeping free hosts.
- Mobile-ready: the same REST endpoints, with push as a later add-on.

**Negative / risks**

- **Latency:** a new message shows within 3 s in an active conversation, and up to 30 s
  in a quiet one. There are no typing indicators or presence.
- **Vercel requests are the chat budget.** Heavy chat use could reach the daily cap: chat
  then slows to one poll a minute until the next UTC day.
- **One database query per poll** while chatting, plus one counter write for the rate
  limit. The chat PR measures this and coarsens the rate-limit window if it costs too much.
- **Not verified:** that the forwarder's per-poll CPU and memory stay small enough on
  Vercel (4 CPU-hours, 360 GB-hours a month). If not, routing the chat paths through a
  Vercel rewrite instead of a function is the first lever (cookies and CSRF through a
  rewrite are untested).

**When to revisit**

- Chat polls exceed 70% of their Vercel share for two weeks in a row.
- Hosting becomes paid and always-on (then option B, with pub/sub, is cheap).
- The product needs typing indicators, presence or sub-second delivery.
- Vercel WebSockets leave beta with a free allowance that fits.
