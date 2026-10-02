import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";
import { isActive } from "./nav";

const navigation = vi.hoisted(() => ({ pathname: "/home" }));
vi.mock("next/navigation", () => ({ usePathname: () => navigation.pathname }));

const USER = { id: "8d3f4b2a-0000-4000-8000-000000000001", email: "ananya@example.com" };

beforeEach(() => {
  navigation.pathname = "/home";
});

function renderShell(props: Partial<Parameters<typeof AppShell>[0]> = {}) {
  return render(
    <AppShell user={USER} {...props}>
      <h1>Page content</h1>
    </AppShell>,
  );
}

describe("AppShell", () => {
  it("has a sidebar and a bottom tab bar, both named Main", () => {
    renderShell();
    const navs = screen.getAllByRole("navigation", { name: "Main" });
    expect(navs).toHaveLength(2);
    const [sidebar, tabs] = navs as [HTMLElement, HTMLElement];
    expect(
      within(sidebar)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Discover", "Messages", "Saved"]);
    expect(
      within(tabs)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Discover", "Messages", "Saved", "You"]);
    expect(screen.getByRole("main")).toHaveTextContent("Page content");
  });

  it("marks the current page and shows Pair spaces as disabled, not a link", () => {
    navigation.pathname = "/messages";
    renderShell();
    const current = screen.getAllByRole("link", { current: "page" });
    expect(current.map((link) => link.textContent)).toEqual(["Messages", "Messages"]);
    expect(screen.queryByRole("link", { name: /Pair spaces/ })).not.toBeInTheDocument();
    expect(screen.getByText("Pair spaces").closest("[aria-disabled]")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(screen.getByText("Pair spaces")).toHaveTextContent("Pair spacesSoon");
  });

  it("gives icon-only and touch controls labels and 44px targets", () => {
    renderShell({ hasNotifications: true });
    const bells = screen.getAllByRole("link", { name: "Notifications (new)" });
    expect(bells).toHaveLength(2); // phone top row and desktop
    for (const bell of bells) expect(bell.className).toMatch(/\bsize-11\b/);
    const tabs = screen.getAllByRole("navigation", { name: "Main" })[1] as HTMLElement;
    for (const tab of within(tabs).getAllByRole("link")) {
      expect(tab.className).toMatch(/\bmin-h-11\b/);
      expect(tab.className).toMatch(/\bmin-w-11\b/);
    }
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
  });

  it("shows unread messages, the profile card and the account link", () => {
    renderShell({ unreadMessages: 2, profileComplete: 78 });
    // Announced in the sidebar badge and on the phone tab (only one is shown at a time).
    expect(screen.getAllByText("2 unread messages")).toHaveLength(2);
    expect(screen.getByRole("meter", { name: "Profile complete" })).toHaveAttribute(
      "aria-valuenow",
      "78",
    );
    expect(screen.getByRole("link", { name: "Your account" })).toHaveAttribute(
      "href",
      "/settings/account",
    );
    expect(screen.getByText(USER.email)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Your profile/ })).toHaveAttribute("href", "/profile");
    expect(screen.getByRole("link", { name: "You" })).toHaveAttribute("href", "/profile");
  });

  it("sends people without a profile to onboarding", () => {
    renderShell({ profileComplete: null });
    expect(screen.getByRole("link", { name: /Your profile/ })).toHaveAttribute(
      "href",
      "/onboarding",
    );
    expect(screen.getByText("Not started")).toBeInTheDocument();
  });

  it("shows the right rail only when given one", () => {
    const { rerender } = renderShell();
    expect(screen.queryByRole("complementary", { name: "Side panel" })).not.toBeInTheDocument();
    rerender(
      <AppShell user={USER} rightRail={<p>Conversations</p>}>
        <p>Body</p>
      </AppShell>,
    );
    expect(screen.getByRole("complementary", { name: "Side panel" })).toHaveTextContent(
      "Conversations",
    );
  });
});

describe("isActive", () => {
  it("matches a path and its children only", () => {
    expect(isActive("/messages", "/messages")).toBe(true);
    expect(isActive("/messages/42", "/messages")).toBe(true);
    expect(isActive("/messagesx", "/messages")).toBe(false);
  });
});
