import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { buildActivity } from "@/lib/home/activity";
import { connection, intro, NOW, request } from "@/lib/home/fixtures";

import { ActivityList } from "./activity-list";
import { Greeting, greetingFor } from "./greeting";
import { EscapeToComposer } from "./escape-to-composer";
import { HomeComposer } from "./home-composer";

const router = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));
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

describe("ActivityList", () => {
  it("filters All, Requests and Messages, from the keyboard too", async () => {
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
    expect(listItems()).toEqual(["/home?item=request-req-1", "/home?item=intro-intro-1"]);

    await user.tab();
    const messages = screen.getByRole("button", { name: "Messages 1" });
    expect(messages).toHaveFocus();
    await user.keyboard(" ");
    expect(listItems()).toEqual(["/home?item=chat-conn-1"]);

    await user.click(screen.getByRole("button", { name: "All" }));
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
    expect(screen.getByText(/No connections yet/)).toBeInTheDocument();
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
    expect(screen.getByText("11/1000")).toBeInTheDocument();
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
