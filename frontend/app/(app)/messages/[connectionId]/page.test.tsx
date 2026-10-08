import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/lib/api/client";
import { connection } from "@/lib/home/fixtures";

import ConversationPage from "./page";

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  cookies: async () => ({ has: () => true, toString: () => "session=x" }),
}));
const NOT_FOUND = vi.hoisted(() => new Error("NEXT_NOT_FOUND"));
vi.mock("next/navigation", () => ({
  redirect: () => {
    throw new Error("NEXT_REDIRECT");
  },
  notFound: () => {
    throw NOT_FOUND;
  },
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/messages/conn-1",
}));
vi.mock("@/lib/api/browser", () => ({ browserApi: vi.fn(() => new Promise(() => undefined)) }));
vi.mock("@/lib/api/client", () => ({ apiRequest: vi.fn() }));

beforeEach(() => {
  vi.mocked(apiRequest).mockImplementation(async (path: string) => {
    if (path === "/api/v1/auth/me") return { id: "me", email: "dev@example.com" };
    if (path === "/api/v1/connections") return { items: [connection()] };
    if (path === "/api/v1/messages/updates") {
      return { items: [], cursor: "c", has_more: false, poll_after_seconds: null };
    }
    if (path.startsWith("/api/v1/connections/conn-1/messages")) {
      return { items: [], next_cursor: null, retention_days: 90 };
    }
    throw new Error(`unexpected call ${path}`);
  });
});

function page(connectionId: string) {
  return ConversationPage({ params: Promise.resolve({ connectionId }) });
}

describe("/messages/[connectionId]", () => {
  it("still opens the chat, with links back to Home's messages and to the pair space", async () => {
    render(await page("conn-1"));
    expect(screen.getByRole("heading", { name: "Aarav R.", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "All messages" })).toHaveAttribute(
      "href",
      "/home?filter=messages",
    );
    expect(screen.getByRole("link", { name: "Open pair space" })).toHaveAttribute(
      "href",
      "/spaces/conn-1",
    );
    // Block and Report sit in the header's "⋯" menu.
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "More actions for Aarav R." }));
    expect(screen.getByRole("button", { name: "Block" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Report" })).toBeInTheDocument();
  });

  it("is not found for a conversation you're not part of", async () => {
    await expect(page("someone-else")).rejects.toBe(NOT_FOUND);
  });
});
