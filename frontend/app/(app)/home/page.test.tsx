import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { browserApi } from "@/lib/api/browser";
import { apiRequest } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { Match, MatchRequest } from "@/lib/api/schemas";
import { connection, intro, request } from "@/lib/home/fixtures";

import MessagesPage from "../messages/page";
import HomeLayout from "./layout";
import HomePage from "./page";

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  cookies: async () => ({ has: () => true, toString: () => "session=x" }),
}));
const REDIRECT = vi.hoisted(() => new Error("NEXT_REDIRECT"));
// `search` is what the inbox and detail panes read from the address (useSearchParams).
const navigation = vi.hoisted(() => ({ redirect: vi.fn(), search: "" }));
vi.mock("next/navigation", () => ({
  redirect: (to: string) => {
    navigation.redirect(to);
    throw REDIRECT;
  },
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(navigation.search),
  usePathname: () => "/home",
}));
// The opened item's own components talk to the API from the browser; keep them quiet.
vi.mock("@/lib/api/browser", () => ({ browserApi: vi.fn(() => new Promise(() => undefined)) }));
vi.mock("@/lib/api/client", () => ({ apiRequest: vi.fn() }));

const USER = { id: "11111111-0000-4000-8000-000000000001", email: "dev@example.com" };
const PROFILE = { about_text: "I build things.", links: [], languages: [], timezone: null };

/** What the Home list may call (design spec 6.2); the shell adds the unread count. */
const LIST_CALLS = [
  "/api/v1/auth/me",
  "/api/v1/me/profile",
  "/api/v1/requests?limit=10",
  "/api/v1/intros?box=received&limit=30",
  "/api/v1/intros?box=sent&limit=30",
  "/api/v1/connections",
];

const MATCH = {
  id: "match-1",
  rank: 1,
  reason: "They offer UI design, which you are looking for.",
  status: "shown",
  candidate: {
    user_id: "33333333-0000-4000-8000-000000000001",
    summary: "Final-year design student.",
    offers: ["UI design"],
    seeks: [],
    interests: [],
    availability: "weekends",
    languages: ["en"],
  },
} as Match;

let failing: string[] = [];
let requestStatus: MatchRequest["status"] = "ready";

beforeEach(() => {
  failing = [];
  requestStatus = "ready";
  vi.mocked(browserApi).mockClear();
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockImplementation(async (path: string) => {
    if (failing.includes(path)) throw new Error("503");
    if (path === "/api/v1/auth/me") return USER;
    if (path === "/api/v1/me/profile") return PROFILE;
    if (path === "/api/v1/requests/req-1/matches") return { items: [MATCH] };
    // One item, by its own endpoint (a request that is not in the list yet is still there).
    if (path === "/api/v1/requests/req-1") return request({ status: requestStatus });
    if (path === "/api/v1/requests/req-2") return request({ id: "req-2", text: "Just created" });
    if (path === "/api/v1/intros/intro-1") return intro();
    if (path.startsWith("/api/v1/requests/") || path.startsWith("/api/v1/intros/")) {
      throw new ApiError(404, undefined, undefined);
    }
    if (path.startsWith("/api/v1/requests")) {
      return { items: [request({ status: requestStatus })], next_cursor: null };
    }
    if (path.startsWith("/api/v1/intros?box=sent")) return { items: [], next_cursor: null };
    if (path.startsWith("/api/v1/intros")) return { items: [intro()], next_cursor: null };
    if (path === "/api/v1/connections") return { items: [connection()] };
    if (path === "/api/v1/messages/updates") {
      return { items: [], cursor: "cursor-1", has_more: false, poll_after_seconds: null };
    }
    if (path.startsWith("/api/v1/connections/conn-1/messages")) {
      return { items: [], next_cursor: null, retention_days: 90 };
    }
    throw new Error(`unexpected call ${path}`);
  });
});

function calledPaths(): string[] {
  return vi.mocked(apiRequest).mock.calls.map(([path]) => path);
}

/** Home as the app renders it: the layout (frame and inbox) around the page (the open item). */
async function renderHome(params: { item?: string; filter?: string } = {}) {
  navigation.search = new URLSearchParams(params).toString();
  render(await HomeLayout({ children: await HomePage({ searchParams: Promise.resolve(params) }) }));
}

describe("Home", () => {
  it("lists requests, intros and chats using only the listed endpoints", async () => {
    await renderHome();
    expect(screen.getByRole("heading", { name: "Home", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Budgeting app design/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /New intro received/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Aarav R\./ })).toBeInTheDocument();
    expect(new Set(calledPaths())).toEqual(new Set(LIST_CALLS));
    expect(screen.getByText(/You're signed in as/)).toHaveTextContent(USER.email);
    // The band sits under the composer.
    for (const band of screen.getAllByRole("link", { name: "Open pair spaces" })) {
      expect(band).toHaveAttribute("href", "/teams");
    }
  });

  it("shows the composer view by default, beside the Inbox (v2)", async () => {
    await renderHome();
    expect(screen.getByRole("heading", { name: "Home", level: 1 })).toHaveClass("sr-only");
    const inbox = screen.getByRole("complementary", { name: "Inbox" });
    expect(within(inbox).getByRole("link", { name: "New request" })).toHaveAttribute(
      "href",
      "/home#new-request",
    );
    expect(within(inbox).queryByRole("form")).not.toBeInTheDocument();
    const composer = screen.getByRole("region", { name: "New request" });
    expect(
      within(composer).getByRole("heading", { name: /What are you building today\?/ }),
    ).toBeInTheDocument();
    expect(within(composer).getByRole("form", { name: "New request" })).toBeInTheDocument();
    expect(within(composer).getByLabelText("Summary")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Opened item" })).not.toBeInTheDocument();
    expect(screen.queryByText("a design partner")).not.toBeInTheDocument();
  });

  it("opens a request from ?item", async () => {
    await renderHome({ item: "request-req-1" });
    const pane = screen.getByRole("region", { name: "Opened item" });
    expect(within(pane).getByText("“Budgeting app design”")).toBeInTheDocument();
    // An opened item replaces the composer view; "New request" goes back to it.
    expect(screen.queryByRole("form", { name: "New request" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New request" })).toHaveAttribute(
      "href",
      "/home#new-request",
    );
    expect(within(pane).getByRole("link", { name: /Inbox/ })).toHaveAttribute("href", "/home");
  });

  it("loads an opened request's matches with the lists, so the browser asks for nothing", async () => {
    await renderHome({ item: "request-req-1" });
    const pane = screen.getByRole("region", { name: "Opened item" });
    expect(within(pane).getByText("Final-year design student.")).toBeInTheDocument();
    expect(new Set(calledPaths())).toEqual(
      new Set([...LIST_CALLS, "/api/v1/requests/req-1", "/api/v1/requests/req-1/matches"]),
    );
    expect(browserApi).not.toHaveBeenCalled();
  });

  it("still opens a request when its matches fail to load: the card asks for them itself", async () => {
    failing = ["/api/v1/requests/req-1/matches"];
    await renderHome({ item: "request-req-1" });
    const pane = screen.getByRole("region", { name: "Opened item" });
    expect(within(pane).getByText("“Budgeting app design”")).toBeInTheDocument();
    expect(browserApi).toHaveBeenCalledWith("/requests/req-1/matches", expect.anything());
  });

  it("keeps a request that is still being matched waiting, whatever the matches call returned", async () => {
    requestStatus = "pending";
    await renderHome({ item: "request-req-1" });
    const pane = screen.getByRole("region", { name: "Opened item" });
    expect(within(pane).getByText("Finding matches")).toBeInTheDocument();
    expect(within(pane).queryByText("Final-year design student.")).not.toBeInTheDocument();
    expect(within(pane).queryByText(/Nobody fits yet/)).not.toBeInTheDocument();
    expect(browserApi).not.toHaveBeenCalled(); // it polls on a timer, not on mount
  });

  it("opens an intro from ?item, with accept, decline, block and report", async () => {
    await renderHome({ item: "intro-intro-1" });
    const pane = screen.getByRole("region", { name: "Opened item" });
    for (const name of [/Accept/, /Decline/, /Block/, /Report/]) {
      expect(within(pane).getAllByRole("button", { name }).length).toBeGreaterThan(0);
    }
  });

  it("opens a chat from ?item, loading only that chat's own calls besides the list", async () => {
    await renderHome({ item: "chat-conn-1" });
    const pane = screen.getByRole("region", { name: "Opened item" });
    expect(within(pane).getByRole("heading", { name: "Aarav R." })).toBeInTheDocument();
    // Block and Report sit in the header's "⋯" menu.
    await userEvent
      .setup()
      .click(within(pane).getByRole("button", { name: "More actions for Aarav R." }));
    expect(within(pane).getByRole("button", { name: "Block" })).toBeInTheDocument();
    expect(within(pane).getByRole("button", { name: "Report" })).toBeInTheDocument();
    expect(new Set(calledPaths())).toEqual(
      new Set([
        ...LIST_CALLS,
        "/api/v1/messages/updates",
        "/api/v1/connections/conn-1/messages?limit=50",
      ]),
    );
  });

  it("says when an item in the address is not there", async () => {
    await renderHome({ item: "chat-someone-else" });
    expect(screen.getByText("This isn't available any more.")).toBeInTheDocument();
  });

  it("shows the error state when a list call fails", async () => {
    failing = ["/api/v1/connections"];
    await renderHome();
    expect(screen.getByRole("alert")).toHaveTextContent("We couldn't load your activity");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("says there are no requests yet, with the composer as the invitation", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path: string) => {
      if (path === "/api/v1/auth/me") return USER;
      if (path === "/api/v1/me/profile") return PROFILE;
      return { items: [], next_cursor: null };
    });
    await renderHome();
    expect(
      screen.getByText("Describe what you're building and we'll find people."),
    ).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "New request" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open pair spaces" })).not.toBeInTheDocument();
  });

  it("sends signed-out visitors to sign in", async () => {
    vi.mocked(apiRequest).mockImplementation(async () => {
      throw new ApiError(401, undefined, undefined);
    });
    await expect(HomeLayout({ children: null })).rejects.toBe(REDIRECT);
    expect(navigation.redirect).toHaveBeenCalledWith("/login?next=/home");
    navigation.redirect.mockClear();
    // An open item checks the session itself: the layout does not re-run when it changes.
    await expect(
      HomePage({ searchParams: Promise.resolve({ item: "request-req-1" }) }),
    ).rejects.toBe(REDIRECT);
    expect(navigation.redirect).toHaveBeenCalledWith("/login?next=/home");
  });
});

describe("Home, opening an item", () => {
  // The layout (with the lists) does not re-run when only ?item= changes, so a click renders
  // the page alone. Its calls are the whole cost of the click.
  it("a request costs the session check, the request and its matches: no lists", async () => {
    render(await HomePage({ searchParams: Promise.resolve({ item: "request-req-1" }) }));
    expect(new Set(calledPaths())).toEqual(
      new Set(["/api/v1/auth/me", "/api/v1/requests/req-1", "/api/v1/requests/req-1/matches"]),
    );
    expect(await screen.findByText("Final-year design student.")).toBeInTheDocument();
  });

  it("an intro costs the session check and the intro", async () => {
    render(await HomePage({ searchParams: Promise.resolve({ item: "intro-intro-1" }) }));
    expect(new Set(calledPaths())).toEqual(new Set(["/api/v1/auth/me", "/api/v1/intros/intro-1"]));
    expect(screen.getByRole("button", { name: /Accept/ })).toBeInTheDocument();
  });

  it("a chat costs the session check, the connections and its own messages", async () => {
    render(await HomePage({ searchParams: Promise.resolve({ item: "chat-conn-1" }) }));
    expect(new Set(calledPaths())).toEqual(
      new Set([
        "/api/v1/auth/me",
        "/api/v1/connections",
        "/api/v1/messages/updates",
        "/api/v1/connections/conn-1/messages?limit=50",
      ]),
    );
    expect(screen.getByRole("heading", { name: "Aarav R." })).toBeInTheDocument();
  });

  it("with nothing open the page renders nothing and calls nothing: the layout has the composer", async () => {
    expect(await HomePage({ searchParams: Promise.resolve({}) })).toBeNull();
    expect(await HomePage({ searchParams: Promise.resolve({ item: "junk" }) })).toBeNull();
    expect(calledPaths()).toEqual([]);
  });

  it("the layout alone makes the list calls, and none for an item", async () => {
    navigation.search = "";
    render(await HomeLayout({ children: null }));
    expect(new Set(calledPaths())).toEqual(new Set(LIST_CALLS));
  });

  it("opens a request that is not in the inbox list yet, such as one just made", async () => {
    await renderHome({ item: "request-req-2" });
    const pane = screen.getByRole("region", { name: "Opened item" });
    expect(within(pane).getByText("“Just created”")).toBeInTheDocument();
  });

  it.each(["request-gone", "intro-gone"])(
    "says %s is not available when it is not there",
    async (item) => {
      await renderHome({ item });
      expect(screen.getByText("This isn't available any more.")).toBeInTheDocument();
    },
  );

  it("takes the first ?item= when the address has several, as the panes do", async () => {
    const page = await HomePage({
      searchParams: Promise.resolve({ item: ["request-req-1", "intro-intro-1"] }),
    });
    expect(page).not.toBeNull();
    expect(calledPaths()).toContain("/api/v1/requests/req-1");
  });
});

describe("/messages", () => {
  it("redirects to Home with the Messages filter", () => {
    expect(() => MessagesPage()).toThrow(REDIRECT);
    expect(navigation.redirect).toHaveBeenCalledWith("/home?filter=messages");
  });
});
