import type { Connection, Intro, MatchRequest } from "@/lib/api/schemas";

/**
 * Home's one activity list (design spec 6.2): requests, intros waiting for an answer and
 * conversations, newest activity first. The API has no merged feed, so the list is built
 * and sorted here from the three existing endpoints.
 */

export type ItemType = "request" | "intro" | "chat";
export type Filter = "all" | "requests" | "messages";

export type ActivityRow = {
  key: string;
  type: ItemType;
  id: string;
  /** For the segmented filter: requests and intros under Requests, chats under Messages. */
  group: Exclude<Filter, "all">;
  title: string;
  secondary: string;
  /** ISO time of the latest activity, for sorting. */
  at: string;
  /** Short relative time: "2m", "1h", "Yesterday", "3 Oct". */
  time: string;
  unread: boolean;
  /** Messages only: who it's with (for the avatar). */
  person?: { userId: string; name: string; photoUrl?: string | null };
};

export const FILTERS: readonly Filter[] = ["all", "requests", "messages"];

export function parseFilter(value: string | undefined): Filter {
  return FILTERS.includes(value as Filter) ? (value as Filter) : "all";
}

/** `?item=<type>-<id>`: which thing is open in the detail pane. */
export function parseItem(value: string | undefined): { type: ItemType; id: string } | null {
  const match = /^(request|intro|chat)-([0-9a-zA-Z-]{1,64})$/.exec(value ?? "");
  if (!match?.[1] || !match[2]) return null;
  return { type: match[1] as ItemType, id: match[2] };
}

export function itemHref(type: ItemType, id: string): string {
  return `/home?item=${type}-${encodeURIComponent(id)}`;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** "now", "2m", "12m", "1h", "Yesterday", then a short date ("3 Oct"). */
export function relativeTime(iso: string, now: Date): string {
  const then = new Date(iso);
  const elapsed = now.getTime() - then.getTime();
  if (elapsed < MINUTE) return "now";
  if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)}m`;
  if (elapsed < DAY) return `${Math.floor(elapsed / HOUR)}h`;
  if (elapsed < 2 * DAY) return "Yesterday";
  return then.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

function requestLine(request: MatchRequest): string {
  switch (request.status) {
    case "pending":
      return "Finding people…";
    case "ready":
      return request.match_count
        ? `${plural(request.match_count, "match", "matches")} ready to view`
        : "Nobody fits yet";
    case "closed":
      return "Closed";
    case "expired":
      return "Expired";
  }
}

export function buildActivity(
  {
    requests,
    intros,
    connections,
  }: { requests: MatchRequest[]; intros: Intro[]; connections: Connection[] },
  now: Date,
): ActivityRow[] {
  const rows: ActivityRow[] = [];
  for (const request of requests) {
    const at = request.matched_at ?? request.created_at;
    rows.push({
      key: `request-${request.id}`,
      type: "request",
      id: request.id,
      group: "requests",
      title: request.title?.trim() || request.text,
      secondary: requestLine(request),
      at,
      time: relativeTime(at, now),
      unread: false,
    });
  }
  for (const intro of intros) {
    if (intro.direction !== "received" || intro.status !== "pending") continue;
    rows.push({
      key: `intro-${intro.id}`,
      type: "intro",
      id: intro.id,
      group: "requests",
      title: "New intro received",
      secondary: `“${intro.request_text}”`,
      at: intro.created_at,
      time: relativeTime(intro.created_at, now),
      unread: false,
    });
  }
  for (const connection of connections) {
    const at = connection.last_message_at ?? connection.created_at;
    const name = connection.person.display_name ?? "Your connection";
    const unread = connection.unread_messages;
    rows.push({
      key: `chat-${connection.id}`,
      type: "chat",
      id: connection.id,
      group: "messages",
      title: name,
      secondary: unread > 0 ? plural(unread, "new message", "new messages") : "Open chat",
      at,
      time: relativeTime(at, now),
      unread: unread > 0,
      person: { userId: connection.person.user_id, name, photoUrl: connection.person.photo_url },
    });
  }
  return rows.sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
}

/** The summary strip: open requests, unread messages, pair spaces (one per connection). */
export function summaryCounts({
  requests,
  connections,
}: {
  requests: MatchRequest[];
  connections: Connection[];
}) {
  return {
    requests: requests.filter((r) => r.status === "pending" || r.status === "ready").length,
    messages: connections.reduce((total, c) => total + c.unread_messages, 0),
    spaces: connections.length,
  };
}
