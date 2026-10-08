import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DeleteAccount, SignOutActions } from "./account-actions";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  router.replace.mockReset();
  document.cookie = "csrf_token=csrf-value-123; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SignOutActions and DeleteAccount", () => {
  it("signs out with the CSRF token and returns to the login page", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const user = userEvent.setup();
    render(<SignOutActions />);

    await user.click(screen.getByRole("button", { name: "Sign out" }));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/auth/logout");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("csrf-value-123");
    expect(init.credentials).toBe("same-origin");
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("signs out of all devices", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    const user = userEvent.setup();
    render(<SignOutActions />);

    await user.click(screen.getByRole("button", { name: "Sign out of all devices" }));

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/auth/logout-all");
    expect(router.replace).toHaveBeenCalledWith("/login");
  });

  it("explains the 30-day grace period and requires confirmation before deleting", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          status: "pending_deletion",
          deletion_scheduled_for: "2026-10-31T10:00:00Z",
          message: "Scheduled.",
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      ),
    );
    const user = userEvent.setup();
    render(<DeleteAccount />);

    await user.click(screen.getByRole("button", { name: "Delete my account…" }));
    const confirm = screen.getByRole("group", { name: "Confirm account deletion" });
    expect(confirm).toHaveTextContent(/permanent deletion in 30 days/);
    const deleteButton = screen.getByRole("button", { name: "Delete my account" });
    expect(deleteButton).toBeDisabled();

    await user.click(screen.getByRole("checkbox", { name: /I understand/ }));
    expect(deleteButton).toBeDisabled();
    await user.type(screen.getByRole("textbox", { name: "Type DELETE to confirm" }), "delete");
    expect(deleteButton).toBeDisabled();
    await user.clear(screen.getByRole("textbox", { name: "Type DELETE to confirm" }));
    await user.type(screen.getByRole("textbox", { name: "Type DELETE to confirm" }), "DELETE");
    await user.click(deleteButton);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/me");
    expect(init.method).toBe("DELETE");
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("csrf-value-123");
    expect(await screen.findByRole("status")).toHaveTextContent(/scheduled for deletion/);
  });

  it("can cancel deleting", async () => {
    const user = userEvent.setup();
    render(<DeleteAccount />);

    await user.click(screen.getByRole("button", { name: "Delete my account…" }));
    expect(screen.getByRole("dialog", { name: "Delete account" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog", { name: "Delete account" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete my account…" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows an error when signing out fails", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: { code: "csrf_failed", message: "x", request_id: null, details: null },
        }),
        { status: 403, headers: { "Content-Type": "application/json" } },
      ),
    );
    const user = userEvent.setup();
    render(<SignOutActions />);

    await user.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Reload the page/);
    expect(router.replace).not.toHaveBeenCalled();
  });
});
