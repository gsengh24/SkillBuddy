import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DeleteAccount, SignOutActions } from "@/components/auth/account-actions";

import { EmailToggle } from "./email-toggle";
import { VisibilityToggle } from "./visibility-toggle";

/*
 * Keyboard and screen-reader checks on the restyled profile and settings controls (PR 6).
 * Wording and behaviour are covered by the existing tests, unchanged.
 */

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(() => new Promise(() => undefined));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("switches", () => {
  it("'Emails about intros' is a named switch that Space turns off", async () => {
    render(<EmailToggle initial />);
    const toggle = screen.getByRole("switch", { name: /Emails about intros/ });
    expect(toggle).toBeChecked();
    toggle.focus();
    await userEvent.setup().keyboard(" ");
    expect(toggle).not.toBeChecked();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("'Show me in new matches' is a named switch reachable by Tab", async () => {
    render(<VisibilityToggle initial="matchable" />);
    await userEvent.setup().tab();
    expect(screen.getByRole("switch", { name: /Show me in new matches/ })).toHaveFocus();
  });
});

describe("account actions", () => {
  it("opens the delete confirmation from the keyboard as a named group", async () => {
    render(<DeleteAccount />);
    const user = userEvent.setup();
    screen.getByRole("button", { name: "Delete my account…" }).focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("group", { name: "Confirm account deletion" })).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Delete my account" });
    expect(confirm).toBeDisabled();
    screen.getByRole("checkbox", { name: /permanently deleted/ }).focus();
    await user.keyboard(" ");
    // DELETE must be typed as well.
    expect(confirm).toBeDisabled();
    screen.getByRole("textbox", { name: "Type DELETE to confirm" }).focus();
    await user.keyboard("DELETE");
    expect(confirm).toBeEnabled();
  });

  it("titles the delete dialog, and offers both ways to sign out", async () => {
    render(
      <>
        <SignOutActions />
        <DeleteAccount />
      </>,
    );
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out of all devices" })).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Delete my account…" }));
    expect(screen.getByRole("dialog", { name: "Delete account" })).toBeInTheDocument();
  });
});
