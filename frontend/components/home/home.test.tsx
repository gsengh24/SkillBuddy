import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { buildActivity } from "@/lib/home/activity";
import { HOME_CHANGED, notifyChatRead } from "@/lib/home/changed";
import { connection, intro, NOW, request } from "@/lib/home/fixtures";

import { ActivityList } from "./activity-list";
import { Greeting, greetingFor } from "./greeting";
import { EscapeToComposer } from "./escape-to-composer";
import { HomeComposer } from "./home-composer";

const router = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/lib/api/browser", () => ({ browserApi: vi.fn() }));

const ROWS = buildActivity(
  {
    requests: [request()],
    intros: [intro()],
    connections: [connection({ id: "conn-1", unread_messages: 2 })],
  },
  NOW,
);

function listItems() {
  const list = screen.queryByRole("list");
  return list
    ? within(list)
        .getAllByRole("link")
        .map((link) => link.getAttribute("href"))
    : [];
}

function screenIs(desktop: boolean) {
  window.matchMedia = vi.fn().mockReturnValue({ matches: desktop }) as never;
  router.replace.mockClear();
}

describe("ActivityList", () => {
  it("opens the newest item of a tab on desktop, and leaves the list alone on a phone", async () => {
    screenIs(true);
    render(<ActivityList rows={ROWS} initialFilter="all" selectedKey={null} />);
    expect(router.replace).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /^Messages/ }));
    expect(router.replace).toHaveBeenCalledWith("/home?item=chat-conn-1");

    screenIs(false);
    await userEvent.click(screen.getByRole("button", { name: /^Requests/ }));
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("clears a chat's unread dot when it is read, until the server sends new rows", () => {
    screenIs(false);
    const { rerender } = render(
      <ActivityList rows={ROWS} initialFilter="all" selectedKey={null} />,
    );
    expect(screen.getByText("Unread messages")).toBeInTheDocument();

    act(() => notifyChatRead("conn-1"));
    expect(screen.queryByText("Unread messages")).not.toBeInTheDocument();
    // Only that chat's dot: its row is still there.
    expect(listItems()).toContain("/home?item=chat-conn-1");

    // A read of some other chat changes nothing here.
    act(() => notifyChatRead("conn-other"));
    expect(screen.queryByText("Unread messages")).not.toBeInTheDocument();

    // Fresh rows from the server (a new message came in) replace what was cleared locally.
    rerender(
      <ActivityList
        rows={buildActivity(
          {
            requests: [request()],
            intros: [intro()],
            connections: [connection({ id: "conn-1", unread_messages: 1 })],
          },
          NOW,
        )}
        initialFilter="all"
        selectedKey={null}
      />,
    );
    expect(screen.getByText("Unread messages")).toBeInTheDocument();
  });

  it("filters All, Requests and Messages, from the keyboard too", async () => {
    screenIs(false);
    render(<ActivityList rows={ROWS} initialFilter="all" selectedKey={null} />);
    expect(listItems()).toEqual([
      "/home?item=request-req-1",
      "/home?item=chat-conn-1",
      "/home?item=intro-intro-1",
    ]);

    const user = userEvent.setup();
    const requests = screen.getByRole("button", { name: "Requests 2" });
    requests.focus();
    await user.keyboard("{Enter}");
    expect(requests).toHaveAttribute("aria-pressed", "true");
    // Requests splits into your requests and the intros you were sent.
    expect(listItems()).toEqual(["/home?item=request-req-1"]);
    await user.click(screen.getByRole("button", { name: "Intros 1" }));
    expect(listItems()).toEqual(["/home?item=intro-intro-1"]);
    await user.click(screen.getByRole("button", { name: "Your requests 1" }));
    expect(listItems()).toEqual(["/home?item=request-req-1"]);

    await user.click(screen.getByRole("button", { name: "Messages 1" }));
    expect(listItems()).toEqual(["/home?item=chat-conn-1"]);

    await user.click(screen.getByRole("button", { name: "All 3" }));
    expect(listItems()).toHaveLength(3);
  });

  it("starts on the filter in the address (/messages leads to Messages)", () => {
    render(<ActivityList rows={ROWS} initialFilter="messages" selectedKey={null} />);
    expect(screen.getByRole("button", { name: "Messages 1" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(listItems()).toEqual(["/home?item=chat-conn-1"]);
  });

  it("gives the unread dot a label and marks the open item", () => {
    render(<ActivityList rows={ROWS} initialFilter="all" selectedKey="chat-conn-1" />);
    const chat = screen.getByRole("link", { name: /Aarav R\./ });
    expect(chat).toHaveAccessibleName(/Unread messages/);
    expect(chat).toHaveAttribute("aria-current", "true");
    expect(chat).toHaveTextContent("2 new messages");
    expect(screen.getByRole("link", { name: /Budgeting app design/ })).toHaveTextContent("Request");
    expect(screen.getByRole("link", { name: /New intro received/ })).toHaveTextContent("Intro");
  });

  it("says why the list is empty, with the old Messages wording for chats", () => {
    render(<ActivityList rows={[]} initialFilter="messages" selectedKey={null} />);
    expect(screen.getByText(/No chats yet/)).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });
});

describe("HomeComposer", () => {
  it("starts collapsed on phones and opens on focus, with every intent and the counter", async () => {
    render(<HomeComposer />);
    const form = screen.getByRole("form", { name: "New request" });
    expect(form).toHaveAttribute("data-open", "false");
    // Collapsed: the chips and counter are hidden below 1024px (shown from lg up).
    const fieldset = screen.getByRole("group", { name: "What kind of help" });
    expect(fieldset.className.split(" ")).toContain("hidden");
    expect(fieldset.className.split(" ")).toContain("lg:flex");

    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Describe it in your own words"));
    expect(form).toHaveAttribute("data-open", "true");
    expect(fieldset.className.split(" ")).not.toContain("hidden");
    expect(
      within(fieldset)
        .getAllByRole("button")
        .map((chip) => chip.textContent),
    ).toEqual([
      "Build together",
      "Skill exchange",
      "Interest buddy",
      "Accountability",
      "Mentor",
      "Explore",
    ]);
    await user.keyboard("learn React");
    expect(screen.getByText("11 / 1000")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "learn React" })).not.toBeInTheDocument();
  });

  it("toggles one intent at a time and sends it", async () => {
    const { browserApi } = await import("@/lib/api/browser");
    vi.mocked(browserApi).mockResolvedValue(request({ id: "new-2", status: "pending" }));
    render(<HomeComposer />);
    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText("Describe it in your own words"),
      "A study group for DSA",
    );
    const mentor = screen.getByRole("button", { name: "Mentor" });
    await user.click(mentor);
    expect(mentor).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Explore" }));
    expect(mentor).toHaveAttribute("aria-pressed", "false");
    await user.click(screen.getByRole("button", { name: "Find matches" }));
    expect(browserApi).toHaveBeenCalledWith("/requests", expect.anything(), {
      method: "POST",
      body: { text: "A study group for DSA", intent: "explore" },
    });
  });

  it("opens the new request after sending it", async () => {
    const { browserApi } = await import("@/lib/api/browser");
    vi.mocked(browserApi).mockResolvedValue(request({ id: "new-1", status: "pending" }));
    render(<HomeComposer />);
    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText("Describe it in your own words"),
      "A designer for a budgeting app",
    );
    await user.click(screen.getByRole("button", { name: "Find matches" }));
    expect(browserApi).toHaveBeenCalledWith("/requests", expect.anything(), {
      method: "POST",
      body: { text: "A designer for a budgeting app", intent: null },
    });
    expect(router.push).toHaveBeenCalledWith("/home?item=request-new-1");
  });

  it("tells the inbox to re-fetch once the new request is opened, and not when sending fails", async () => {
    const { browserApi } = await import("@/lib/api/browser");
    const changed = vi.fn();
    window.addEventListener(HOME_CHANGED, changed);
    router.push.mockClear();
    try {
      vi.mocked(browserApi).mockRejectedValueOnce(new Error("503"));
      render(<HomeComposer />);
      const user = userEvent.setup();
      await user.type(screen.getByLabelText("Describe it in your own words"), "A designer, please");
      await user.click(screen.getByRole("button", { name: "Find matches" }));
      expect(changed).not.toHaveBeenCalled();
      expect(router.push).not.toHaveBeenCalled();

      vi.mocked(browserApi).mockResolvedValueOnce(request({ id: "new-2", status: "pending" }));
      await user.type(screen.getByLabelText("Describe it in your own words"), " for budgeting");
      await user.click(screen.getByRole("button", { name: "Find matches" }));
      expect(changed).toHaveBeenCalledTimes(1);
      // Queued after the navigation, so the refreshed lists include the new request.
      expect(router.push.mock.invocationCallOrder[0]).toBeLessThan(
        changed.mock.invocationCallOrder[0] ?? 0,
      );
    } finally {
      window.removeEventListener(HOME_CHANGED, changed);
    }
  });
});

describe("EscapeToComposer", () => {
  it("goes back to the composer view on Escape, but not while typing in a field", async () => {
    render(
      <>
        <EscapeToComposer href="/home?filter=messages" />
        <textarea aria-label="Message" />
      </>,
    );
    const user = userEvent.setup();
    router.push.mockClear();
    screen.getByLabelText("Message").focus();
    await user.keyboard("{Escape}");
    expect(router.push).not.toHaveBeenCalled();
    (document.activeElement as HTMLElement).blur();
    await user.keyboard("{Escape}");
    expect(router.push).toHaveBeenCalledWith("/home?filter=messages");
  });
});

describe("Greeting", () => {
  it.each([
    [7, "Good morning"],
    [13, "Good afternoon"],
    [20, "Good evening"],
  ])("at %i:00 says %s", (hour, text) => {
    expect(greetingFor(hour)).toBe(text);
  });

  it("says Hello in the server HTML, before the browser knows its clock", () => {
    expect(renderToString(<Greeting />)).toContain("Hello");
  });

  it("uses this device's clock in the browser", () => {
    render(<Greeting />);
    expect(screen.getByText(greetingFor(new Date().getHours()))).toBeInTheDocument();
  });
});

describe("QuickRespond in the All list", () => {
  it("accepts an incoming intro from its row and removes the row", async () => {
    screenIs(false);
    const { browserApi } = await import("@/lib/api/browser");
    vi.mocked(browserApi).mockResolvedValue(intro({ status: "accepted" }));
    render(<ActivityList rows={ROWS} initialFilter="all" selectedKey={null} />);
    await userEvent.click(screen.getByRole("button", { name: "Accept intro" }));
    expect(browserApi).toHaveBeenCalledWith(
      "/intros/intro-1/respond",
      expect.anything(),
      expect.objectContaining({ body: { accept: true } }),
    );
    expect(listItems()).not.toContain("/home?item=intro-intro-1");
  });

  it("shows no buttons on an intro you sent", () => {
    screenIs(false);
    const rows = buildActivity(
      { requests: [], intros: [intro({ direction: "sent" })], connections: [] },
      NOW,
    );
    render(<ActivityList rows={rows} initialFilter="all" selectedKey={null} />);
    expect(screen.queryByRole("button", { name: "Decline intro" })).toBeNull();
  });
});
