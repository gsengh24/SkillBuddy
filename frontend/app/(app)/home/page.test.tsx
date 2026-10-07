import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { connection, intro, request } from "@/lib/home/fixtures";

import MessagesPage from "../messages/page";
import HomePage from "./page";

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  cookies: async () => ({ has: () => true, toString: () => "session=x" }),
}));
const REDIRECT = vi.hoisted(() => new Error("NEXT_REDIRECT"));
const navigation = vi.hoisted(() => ({ redirect: vi.fn() }));
vi.mock("next/navigation", () => ({
  redirect: (to: string) => {
    navigation.redirect(to);
    throw REDIRECT;
  },
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
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
  "/api/v1/connections",
];

let failing: string[] = [];

beforeEach(() => {
  failing = [];
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockImplementation(async (path: string) => {
    if (failing.includes(path)) throw new Error("503");
    if (path === "/api/v1/auth/me") return USER;
    if (path === "/api/v1/me/profile") return PROFILE;
    if (path.startsWith("/api/v1/requests")) return { items: [request()], next_cursor: null };
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

async function renderHome(params: { item?: string; filter?: string } = {}) {
  render(await HomePage({ searchParams: Promise.resolve(params) }));
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
    // The band shows twice: after the list on phones, beside the summary on desktop.
    for (const band of screen.getAllByRole("link", { name: "Open pair spaces" })) {
      expect(band).toHaveAttribute("href", "/spaces");
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
    expect(within(pane).getByRole("link", { name: /Back to Home/ })).toHaveAttribute(
      "href",
      "/home",
    );
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
    expect(within(pane).getByRole("link", { name: "Open pair space" })).toHaveAttribute(
      "href",
      "/spaces/conn-1",
    );
    expect(within(pane).getByRole("button", { name: /Block/ })).toBeInTheDocument();
    expect(within(pane).getByRole("button", { name: /Report/ })).toBeInTheDocument();
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
      screen.getByText("No requests yet. Describe what you're building and we'll find people."),
    ).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "New request" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open pair spaces" })).not.toBeInTheDocument();
  });

  it("sends signed-out visitors to sign in", async () => {
    vi.mocked(apiRequest).mockImplementation(async () => {
      throw new ApiError(401, undefined, undefined);
    });
    await expect(HomePage({ searchParams: Promise.resolve({}) })).rejects.toBe(REDIRECT);
    expect(navigation.redirect).toHaveBeenCalledWith("/login?next=/home");
  });
});

describe("/messages", () => {
  it("redirects to Home with the Messages filter", () => {
    expect(() => MessagesPage()).toThrow(REDIRECT);
    expect(navigation.redirect).toHaveBeenCalledWith("/home?filter=messages");
  });
});
