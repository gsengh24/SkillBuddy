import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";
import { isActive } from "./links";

const navigation = vi.hoisted(() => ({ pathname: "/home" }));
vi.mock("next/navigation", () => ({ usePathname: () => navigation.pathname }));

const USER = { id: "8d3f4b2a-0000-4000-8000-000000000001", email: "ananya@example.com" };
const PLACES = ["Home", "Spaces", "Saved", "You"];

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

function navs() {
  const [desktop, phone] = screen.getAllByRole("navigation", { name: "Main" }) as [
    HTMLElement,
    HTMLElement,
  ];
  return { desktop, phone };
}

describe("AppShell", () => {
  it("has a desktop top bar and a phone bottom nav, both named Main, with the same places", () => {
    renderShell();
    const { desktop, phone } = navs();
    expect(
      within(desktop)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(PLACES);
    expect(
      within(phone)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(PLACES);
    expect(within(desktop).getByRole("link", { name: "You" })).toHaveAttribute("href", "/you");
    expect(screen.getByRole("main")).toHaveTextContent("Page content");
    expect(screen.queryByText("Soon")).not.toBeInTheDocument();
  });

  it.each([
    ["/home", "Home"],
    ["/spaces/42", "Spaces"],
    ["/saved", "Saved"],
    ["/you", "You"],
    ["/settings/blocked", "You"],
  ])("marks the current place on %s in both navs", (pathname, label) => {
    navigation.pathname = pathname;
    renderShell();
    const current = screen.getAllByRole("link", { current: "page" });
    expect(current.map((link) => link.textContent)).toEqual([label, label]);
  });

  it("counts chats as Home, with no separate Messages link", () => {
    navigation.pathname = "/messages/42";
    renderShell();
    const current = screen.getAllByRole("link", { current: "page" });
    expect(current.map((link) => link.textContent)).toEqual(["Home", "Home"]);
    expect(screen.queryByRole("link", { name: /^Messages/ })).not.toBeInTheDocument();
  });

  it("gives icon-only and touch controls labels and 44px targets", () => {
    renderShell({ hasNotifications: true });
    const bells = screen.getAllByRole("link", { name: "Notifications (new)" });
    expect(bells).toHaveLength(2); // phone top row and desktop
    for (const bell of bells) {
      expect(bell).toHaveAttribute("href", "/notifications");
      expect(bell.className).toMatch(/\bsize-11\b/);
    }
    for (const tab of within(navs().phone).getAllByRole("link")) {
      expect(tab.className).toMatch(/\bmin-h-11\b/);
    }
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
  });

  it("can be used from the keyboard: skip link first, then the navigation in order", async () => {
    renderShell();
    const user = userEvent.setup();
    await user.tab();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveFocus();

    const { desktop } = navs();
    const order: string[] = [];
    for (let step = 0; step < 6; step += 1) {
      await user.tab();
      const focused = document.activeElement;
      if (focused && desktop.contains(focused)) order.push(focused.textContent ?? "");
    }
    expect(order).toEqual(PLACES);
  });

  it("shows profile progress and the account link", () => {
    renderShell({ profileComplete: 78 });
    expect(screen.getByRole("meter", { name: "Profile complete" })).toHaveAttribute(
      "aria-valuenow",
      "78",
    );
    expect(screen.getByRole("link", { name: /Your profile/ })).toHaveAttribute("href", "/you");
    const account = screen.getByRole("link", { name: "Your account" });
    expect(account).toHaveAttribute("href", "/you#s-security");
    expect(account).toHaveAttribute("title", USER.email);
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
