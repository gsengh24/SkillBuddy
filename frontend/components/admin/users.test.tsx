import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { UserDetail } from "@/lib/admin/schemas";

import { UserDrawer } from "./users";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const USER: UserDetail = {
  id: "u1",
  email: "sam@example.com",
  status: "active",
  suspended_until: null,
  deletion_scheduled_for: null,
  created_at: "2026-10-01T10:00:00Z",
  last_login_at: null,
  email_verified_at: "2026-10-01T10:00:00Z",
  sign_in_methods: ["email"],
  profile: {
    display_name: "Sam",
    headline: "",
    city: "",
    about_text: "<script>alert(1)</script> I build apps.",
    intents: [],
    visibility: "matchable",
    parse_status: "parsed",
  },
  counts: { requests: 2, reports_against: 0 },
  timeline: [{ at: "2026-10-01T10:00:00Z", event: "account.created" }],
  notes: [],
};

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);
  router.refresh.mockReset();
  router.push.mockReset();
  document.cookie = "csrf_token=csrf-value-123; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const MODERATOR = ["view_dashboards", "view_users", "suspend_users", "handle_reports"];

describe("UserDrawer", () => {
  it("shows user text as plain text", () => {
    render(<UserDrawer user={USER} permissions={MODERATOR} closeHref="/admin/users" />);
    expect(screen.getByText("<script>alert(1)</script> I build apps.")).toBeInTheDocument();
  });

  it("hides every action from read-only admins", () => {
    render(
      <UserDrawer
        user={USER}
        permissions={["view_dashboards", "view_users"]}
        closeHref="/admin/users"
      />,
    );
    expect(screen.queryByRole("group", { name: "Actions" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Add a private note")).not.toBeInTheDocument();
  });

  it("gives moderators every action but deletion", () => {
    render(<UserDrawer user={USER} permissions={MODERATOR} closeHref="/admin/users" />);
    const actions = screen.getByRole("group", { name: "Actions" });
    expect(within(actions).getByRole("button", { name: "Suspend for 7 days" })).toBeInTheDocument();
    expect(within(actions).getByRole("button", { name: "Ban" })).toBeInTheDocument();
    expect(
      within(actions).queryByRole("button", { name: "Schedule deletion" }),
    ).not.toBeInTheDocument();
  });

  it("needs a 10-character reason and sends it with the action", async () => {
    const user = userEvent.setup({ delay: null });
    render(<UserDrawer user={USER} permissions={MODERATOR} closeHref="/admin/users" />);
    await user.click(screen.getByRole("button", { name: "Ban" }));
    const dialog = screen.getByRole("dialog", { name: "Ban" });
    const confirm = within(dialog).getByRole("button", { name: "Confirm" });
    await user.type(within(dialog).getByLabelText(/Reason/), "spam");
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/Reason/), " links in every intro");
    await user.click(confirm);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/admin/users/u1/ban");
    expect(JSON.parse(String(init.body))).toEqual({ reason: "spam links in every intro" });
    expect(router.refresh).toHaveBeenCalled();
  });
});
