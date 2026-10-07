import { describe, expect, it } from "vitest";

import {
  buildActivity,
  itemHref,
  parseFilter,
  parseItem,
  relativeTime,
  summaryCounts,
} from "./activity";
import { connection, intro, minutesAgo, NOW, request } from "./fixtures";

describe("buildActivity", () => {
  it("merges requests, waiting intros and chats, newest activity first", () => {
    const rows = buildActivity(
      {
        requests: [request({ matched_at: minutesAgo(2) })],
        intros: [intro({ created_at: minutesAgo(60) })],
        connections: [
          connection({ id: "conn-1", last_message_at: minutesAgo(12) }),
          connection({ id: "conn-2", last_message_at: minutesAgo(60 * 30), unread_messages: 0 }),
        ],
      },
      NOW,
    );
    expect(rows.map((row) => row.key)).toEqual([
      "request-req-1",
      "chat-conn-1",
      "intro-intro-1",
      "chat-conn-2",
    ]);
    expect(rows.map((row) => row.time)).toEqual(["2m", "12m", "1h", "Yesterday"]);
  });

  it("describes each row as the spec says, with no message text", () => {
    const [requestRow, introRow, unreadChat, readChat] = buildActivity(
      {
        requests: [request({ match_count: 4, matched_at: minutesAgo(1) })],
        intros: [intro({ created_at: minutesAgo(3) })],
        connections: [
          connection({ id: "a", unread_messages: 2, last_message_at: minutesAgo(5) }),
          connection({ id: "b", unread_messages: 0, last_message_at: minutesAgo(9) }),
        ],
      },
      NOW,
    );
    expect(requestRow).toMatchObject({ group: "requests", secondary: "4 matches ready to view" });
    expect(introRow).toMatchObject({
      group: "requests",
      title: "New intro received",
      secondary: "“React basics”",
    });
    expect(unreadChat).toMatchObject({
      group: "messages",
      title: "Aarav R.",
      secondary: "2 new messages",
      unread: true,
    });
    expect(readChat).toMatchObject({ secondary: "Open chat", unread: false });
  });

  it("names a connection only when the API gives a name, as today", () => {
    const [row] = buildActivity(
      {
        requests: [],
        intros: [],
        connections: [connection({ person: { ...connection().person, display_name: null } })],
      },
      NOW,
    );
    expect(row?.title).toBe("Your connection");
  });

  it("lists only intros received and still waiting", () => {
    const rows = buildActivity(
      {
        requests: [],
        intros: [
          intro({ id: "waiting" }),
          intro({ id: "answered", status: "accepted" }),
          intro({ id: "sent", direction: "sent" }),
        ],
        connections: [],
      },
      NOW,
    );
    expect(rows.map((row) => row.id)).toEqual(["waiting"]);
  });

  it.each([
    ["pending", 0, "Finding people…"],
    ["ready", 1, "1 match ready to view"],
    ["ready", 0, "Nobody fits yet"],
    ["closed", 2, "Closed"],
    ["expired", 0, "Expired"],
  ] as const)("says what a %s request with %i matches is doing", (status, count, line) => {
    const [row] = buildActivity(
      { requests: [request({ status, match_count: count })], intros: [], connections: [] },
      NOW,
    );
    expect(row?.secondary).toBe(line);
  });
});

describe("relativeTime", () => {
  it.each([
    [0.5, "now"],
    [2, "2m"],
    [59, "59m"],
    [60, "1h"],
    [60 * 23, "23h"],
    [60 * 30, "Yesterday"],
    [60 * 24 * 5, "3 Oct"],
  ])("%i minutes ago is %s", (minutes, label) => {
    expect(relativeTime(minutesAgo(minutes), NOW)).toBe(label);
  });
});

describe("items and filters in the address", () => {
  it("round-trips ?item for each type", () => {
    for (const type of ["request", "intro", "chat"] as const) {
      const href = itemHref(type, "abc-123");
      const value = new URL(href, "https://x").searchParams.get("item") ?? undefined;
      expect(parseItem(value)).toEqual({ type, id: "abc-123" });
    }
  });

  it("ignores anything else", () => {
    expect(parseItem(undefined)).toBeNull();
    expect(parseItem("profile-1")).toBeNull();
    expect(parseItem("chat-../../x")).toBeNull();
    expect(parseFilter("messages")).toBe("messages");
    expect(parseFilter("everything")).toBe("all");
    expect(parseFilter(undefined)).toBe("all");
  });
});

describe("summaryCounts", () => {
  it("counts open requests, unread messages and pair spaces", () => {
    expect(
      summaryCounts({
        requests: [request(), request({ status: "pending" }), request({ status: "closed" })],
        connections: [connection({ unread_messages: 2 }), connection({ unread_messages: 1 })],
      }),
    ).toEqual({ requests: 2, messages: 3, spaces: 2 });
  });
});
