import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Message } from "@/lib/api/schemas";
import { delayAfterError, nextPollDelay } from "@/lib/chat/cadence";

import { Conversation } from "./conversation";

const ME = "11111111-0000-4000-8000-000000000001";
const THEM = "11111111-0000-4000-8000-000000000002";
const CONNECTION = "55555555-0000-4000-8000-000000000001";

function message(id: number, sender: string, body: string): Message {
  return {
    id: `66666666-0000-4000-8000-${String(id).padStart(12, "0")}`,
    connection_id: CONNECTION,
    sender_id: sender,
    body,
    created_at: `2026-10-03T10:0${id}:00Z`,
  };
}

function json(status: number, body?: unknown, headers: Record<string, string> = {}): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function updates(items: Message[], extra: Record<string, unknown> = {}) {
  return { items, cursor: `c${items.length}`, has_more: false, poll_after_seconds: null, ...extra };
}

let fetchMock: ReturnType<typeof vi.fn>;
const pollCalls = () =>
  fetchMock.mock.calls.filter(([url]) => String(url).startsWith("/api/v1/messages/updates"));
const readCalls = () =>
  fetchMock.mock.calls.filter(([url]) => String(url).endsWith(`/connections/${CONNECTION}/read`));

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fetchMock = vi.fn(async (url: string) =>
    String(url).endsWith("/read") ? json(204) : json(200, updates([])),
  );
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function renderConversation(initial: Message[] = [], hasUnread = false) {
  return render(
    <Conversation
      connectionId={CONNECTION}
      meId={ME}
      otherId={THEM}
      otherName="Asha"
      initial={initial}
      cursor="start"
      retentionDays={90}
      hasUnread={hasUnread}
    />,
  );
}

describe("poll cadence (ADR 0012)", () => {
  it("slows down as a conversation goes quiet, then stops", () => {
    expect(nextPollDelay(0)).toBe(3_000);
    expect(nextPollDelay(59_000)).toBe(3_000);
    expect(nextPollDelay(61_000)).toBe(10_000);
    expect(nextPollDelay(4 * 60_000)).toBe(10_000);
    expect(nextPollDelay(6 * 60_000)).toBe(30_000);
    expect(nextPollDelay(10 * 60_000)).toBeNull();
  });

  it("honours the server's minimum and Retry-After", () => {
    expect(nextPollDelay(0, 60)).toBe(60_000);
    expect(delayAfterError(20)).toBe(20_000);
    expect(delayAfterError()).toBe(60_000);
  });
});

describe("Conversation", () => {
  it("shows messages oldest first, who said what, and the retention note", () => {
    renderConversation([message(2, THEM, "Hi back"), message(1, ME, "Hello")]);
    const items = within(screen.getByRole("list", { name: "Messages" }))
      .getAllByRole("listitem")
      .filter((li) => li.textContent);
    expect(items.map((li) => li.querySelector("p")?.textContent)).toEqual([
      "You: Hello",
      "Asha: Hi back",
    ]);
    expect(screen.getByText("Messages are deleted 90 days after they're sent.")).toBeVisible();
  });

  it("shows the safety tips at the start of a chat, and not once it has 10 messages", () => {
    const { unmount } = renderConversation([message(1, THEM, "Hi")]);
    expect(screen.getByText("Staying safe")).toBeVisible();
    expect(screen.getByText(/Never send money or bank details/)).toBeVisible();
    unmount();

    const ten = Array.from({ length: 10 }, (_, i) => message(i + 1, i % 2 ? ME : THEM, `m${i}`));
    renderConversation(ten);
    expect(screen.queryByText("Staying safe")).not.toBeInTheDocument();
  });

  it("marks the conversation read when it opens with unread messages", async () => {
    renderConversation([message(1, THEM, "Hi")], true);
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(readCalls()).toHaveLength(1);
  });

  it("sends a message and shows it", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const sent = message(3, ME, "Friday works");
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) =>
      init?.method === "POST" && String(url).endsWith("/messages")
        ? json(201, sent)
        : json(200, updates([])),
    );
    renderConversation();

    await user.type(screen.getByLabelText("Message Asha"), "  Friday works  ");
    await user.click(screen.getByRole("button", { name: "Send" }));

    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(post?.[0]).toBe(`/api/v1/connections/${CONNECTION}/messages`);
    expect(JSON.parse(post?.[1]?.body as string)).toEqual({ body: "Friday works" });
    expect(await screen.findByText("Friday works")).toBeInTheDocument();
    expect(screen.getByLabelText("Message Asha")).toHaveValue("");
  });

  it("polls every 3 s, adds new messages once, and marks theirs read", async () => {
    const incoming = message(4, THEM, "See you then");
    let call = 0;
    fetchMock.mockImplementation(async (url: string) => {
      if (String(url).endsWith("/read")) return json(204);
      call += 1;
      // The same recent message comes back twice (the API's visibility lag).
      return json(200, updates(call <= 2 ? [incoming] : []));
    });
    renderConversation();

    await act(() => vi.advanceTimersByTimeAsync(3_100));
    expect(pollCalls()[0]?.[0]).toBe("/api/v1/messages/updates?after=start");
    await act(() => vi.advanceTimersByTimeAsync(3_100));
    expect(pollCalls()[1]?.[0]).toBe("/api/v1/messages/updates?after=c1");

    expect(screen.getAllByText("See you then")).toHaveLength(1);
    expect(readCalls()).toHaveLength(1);
  });

  it("ignores other conversations' messages in the shared poll", async () => {
    fetchMock.mockResolvedValue(
      json(200, updates([{ ...message(5, THEM, "Elsewhere"), connection_id: "other" }])),
    );
    renderConversation();
    await act(() => vi.advanceTimersByTimeAsync(3_100));
    expect(screen.queryByText("Elsewhere")).not.toBeInTheDocument();
  });

  it("stops after 10 quiet minutes and resumes on request", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderConversation();

    await act(() => vi.advanceTimersByTimeAsync(11 * 60_000));
    expect(screen.getByRole("status")).toHaveTextContent("Paused while it's quiet");
    const pollsWhenPaused = pollCalls().length;
    await act(() => vi.advanceTimersByTimeAsync(10 * 60_000));
    expect(pollCalls()).toHaveLength(pollsWhenPaused);

    await user.click(screen.getByRole("button", { name: "Check for messages" }));
    await act(() => vi.advanceTimersByTimeAsync(10));
    expect(pollCalls()).toHaveLength(pollsWhenPaused + 1);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("does not poll while the tab is hidden", async () => {
    const visibility = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    renderConversation();
    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(pollCalls()).toHaveLength(0);

    visibility.mockReturnValue("visible");
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await act(() => vi.advanceTimersByTimeAsync(10));
    expect(pollCalls()).toHaveLength(1);
  });

  it("slows to the server's pace when the daily budget is spent", async () => {
    fetchMock.mockResolvedValue(json(200, updates([], { poll_after_seconds: 60 })));
    renderConversation();
    await act(() => vi.advanceTimersByTimeAsync(3_100));
    expect(pollCalls()).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(30_000));
    expect(pollCalls()).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(31_000));
    expect(pollCalls()).toHaveLength(2);
  });

  it("shows why a message could not be sent", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    fetchMock.mockImplementation(async (_url: string, init?: RequestInit) =>
      init?.method === "POST"
        ? json(409, {
            error: { code: "conversation_closed", message: "x", request_id: null, details: null },
          })
        : json(200, updates([])),
    );
    renderConversation();
    await user.type(screen.getByLabelText("Message Asha"), "Hello?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("This person can't receive messages right now.")).toBeVisible();
  });
});
