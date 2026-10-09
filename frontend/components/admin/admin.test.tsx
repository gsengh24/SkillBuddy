import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { menuCounts, pagesFor } from "@/lib/admin/pages";

import { AdminShell } from "./admin-shell";
import { AuditLog, InviteAdmin } from "./team-actions";
import { TwoStepForm } from "./two-step-form";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
let pathname = "/admin";
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => pathname }));

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  router.replace.mockReset();
  router.refresh.mockReset();
  router.push.mockReset();
  document.cookie = "csrf_token=csrf-value-123; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const OWNER = [
  "view_dashboards",
  "view_users",
  "suspend_users",
  "handle_reports",
  "read_reported_messages",
  "manage_signup",
  "manage_settings",
  "manage_ai",
  "manage_admins",
  "delete_data",
];

describe("pagesFor", () => {
  it("shows each role the pages in the reference", () => {
    const labels = (permissions: string[]) => pagesFor(permissions).map((page) => page.slug);
    expect(labels(OWNER)).toHaveLength(10);
    expect(labels(OWNER.filter((p) => p !== "manage_admins"))).not.toContain("team");
    expect(labels(["view_dashboards", "view_users", "suspend_users", "handle_reports"])).toEqual([
      "",
      "users",
      "reports",
      "content",
    ]);
    expect(labels(["view_dashboards", "view_users"])).toEqual(["", "users", "reports", "content"]);
  });
});

describe("AdminShell", () => {
  it("lists the role's pages, marks the current one and opens on phones", async () => {
    pathname = "/admin/team";
    render(
      <AdminShell pages={pagesFor(OWNER)} role="owner" name="owner" environment="Preview">
        <p>Page</p>
      </AdminShell>,
    );
    const nav = screen.getByRole("navigation", { name: "Admin" });
    expect(within(nav).getByRole("link", { name: "Team and audit" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByText("Preview")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
    const menu = screen.getByRole("button", { name: "Open menu" });
    await userEvent.setup({ delay: null }).click(menu);
    expect(screen.getByRole("button", { name: "Close menu" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("searches users from the top bar and ends only the admin session", async () => {
    pathname = "/admin";
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    render(
      <AdminShell pages={pagesFor(OWNER)} role="owner" name="owner" environment="Preview">
        <p>Page</p>
      </AdminShell>,
    );
    const search = screen.getByRole("searchbox", { name: "Search users by name or email" });
    expect(search).toHaveAttribute("name", "q");
    expect(search.closest("form")).toHaveAttribute("action", "/admin/users");

    await userEvent.setup({ delay: null }).click(screen.getByRole("button", { name: "Sign out" }));
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/admin/sign-out");
    expect(init.method).toBe("POST");
    expect(router.push).toHaveBeenCalledWith("/home");
  });

  it("shows how many items wait beside a menu entry, and nothing for zero", () => {
    pathname = "/admin";
    const counts = menuCounts({ open_reports: 4, pending_applications: 0, failed_emails: 2 });
    expect(counts).toEqual({ reports: 4 });
    render(
      <AdminShell
        pages={pagesFor(OWNER)}
        counts={counts}
        role="owner"
        name="owner"
        environment="Preview"
      >
        <p>Page</p>
      </AdminShell>,
    );
    const nav = screen.getByRole("navigation", { name: "Admin" });
    expect(within(nav).getByRole("link", { name: "Reports and safety, 4 waiting" })).toBeVisible();
    expect(within(nav).getByRole("link", { name: "Signup and access" })).toBeVisible();
  });

  it("leaves out pages a moderator can't open", () => {
    pathname = "/admin";
    render(
      <AdminShell
        pages={pagesFor(["view_dashboards", "view_users", "handle_reports"])}
        role="moderator"
        name="mod"
        environment="Production"
      >
        <p>Page</p>
      </AdminShell>,
    );
    expect(screen.queryByRole("link", { name: "Team and audit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  });
});

describe("TwoStepForm", () => {
  it("sets up two-step login and shows the recovery codes once", async () => {
    fetchMock
      .mockResolvedValueOnce(json(200, { secret: "ABCDEFGHIJKLMNOP", otpauth_uri: "otpauth://x" }))
      .mockResolvedValueOnce(
        json(200, { expires_at: "2026-10-08T12:30:00Z", recovery_codes: ["aaaa-bbbb-cccc"] }),
      );
    const user = userEvent.setup({ delay: null });
    render(<TwoStepForm enabled={false} />);

    await user.click(screen.getByRole("button", { name: "Set up two-step login" }));
    expect(screen.getByText("ABCD EFGH IJKL MNOP")).toBeInTheDocument();
    await user.type(screen.getByLabelText("First code from the app"), "123456");
    await user.click(screen.getByRole("button", { name: "Turn on two-step login" }));

    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/admin/two-step/confirm");
    expect(screen.getByRole("list", { name: "Recovery codes" })).toHaveTextContent(
      "aaaa-bbbb-cccc",
    );
    await user.click(screen.getByRole("button", { name: "I've saved them" }));
    expect(router.replace).toHaveBeenCalledWith("/admin");
  });

  it("verifies a code and says when it is wrong", async () => {
    fetchMock
      .mockResolvedValueOnce(
        json(400, {
          error: { code: "invalid_two_step_code", message: "x", request_id: null, details: null },
        }),
      )
      .mockResolvedValueOnce(json(200, { expires_at: "2026-10-08T12:30:00Z" }));
    const user = userEvent.setup({ delay: null });
    render(<TwoStepForm enabled />);
    const field = screen.getByLabelText("Code from your authenticator app");
    await user.type(field, "000000");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("didn't work");
    await user.clear(field);
    await user.type(field, "123456");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/admin/two-step/verify");
    expect(router.replace).toHaveBeenCalledWith("/admin");
  });
});

describe("InviteAdmin", () => {
  it("needs a 10-character reason and sends email, role and reason", async () => {
    fetchMock.mockResolvedValueOnce(
      json(201, {
        user_id: "u2",
        email: "helper@example.com",
        role: "readonly",
        from_environment: false,
        two_step_enabled: false,
        last_active_at: null,
      }),
    );
    const user = userEvent.setup({ delay: null });
    render(<InviteAdmin />);
    await user.click(screen.getByRole("button", { name: "Invite admin" }));
    const dialog = screen.getByRole("dialog", { name: "Invite an admin" });
    await user.type(within(dialog).getByLabelText("Email"), "helper@example.com");
    await user.selectOptions(within(dialog).getByLabelText("Role"), "readonly");
    const give = within(dialog).getByRole("button", { name: "Give the role" });
    await user.type(within(dialog).getByLabelText(/Reason/), "short");
    expect(give).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/Reason/), " but long enough now");
    await user.click(give);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/admin/team");
    expect(JSON.parse(String(init.body))).toEqual({
      email: "helper@example.com",
      role: "readonly",
      reason: "short but long enough now",
    });
    expect(router.refresh).toHaveBeenCalled();
  });
});

describe("AuditLog", () => {
  it("shows entries as plain text and loads older ones", async () => {
    const entry = {
      id: "a1",
      created_at: "2026-10-08T10:00:00Z",
      actor_id: "u1",
      actor_role: "owner",
      action: "admin.role_granted.moderator",
      target_type: "user",
      target_id: "u2",
      reason: "<b>not bold</b>",
      ip: "198.51.100.1",
    };
    fetchMock.mockResolvedValueOnce(
      json(200, { items: [{ ...entry, id: "a2", action: "admin.signed_in" }], next_cursor: null }),
    );
    render(<AuditLog initial={[entry]} initialCursor="c1" />);
    expect(screen.getByText("<b>not bold</b>")).toBeInTheDocument();
    await userEvent
      .setup({ delay: null })
      .click(screen.getByRole("button", { name: "Show older entries" }));
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/admin/audit?limit=50&cursor=c1");
    expect(screen.getByText("admin.signed_in")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show older entries" })).not.toBeInTheDocument();
  });

  it("filters by an exact action and keeps the filter when loading older entries", async () => {
    const entry = {
      id: "a1",
      created_at: "2026-10-08T10:00:00Z",
      actor_id: "u1",
      actor_role: "owner",
      action: "admin.signed_in",
      target_type: null,
      target_id: null,
      reason: null,
      ip: null,
    };
    const banned = { ...entry, id: "a2", action: "user.banned" };
    fetchMock
      .mockResolvedValueOnce(json(200, { items: [banned], next_cursor: "c2" }))
      .mockResolvedValueOnce(json(200, { items: [], next_cursor: null }))
      .mockResolvedValueOnce(json(200, { items: [], next_cursor: null }));
    const user = userEvent.setup({ delay: null });
    render(<AuditLog initial={[entry]} initialCursor={null} />);

    await user.type(screen.getByLabelText("Exactly"), "user.banned");
    await user.click(screen.getByRole("button", { name: "Filter" }));
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/admin/audit?limit=50&action=user.banned");
    expect(screen.getByText("user.banned")).toBeInTheDocument();
    expect(screen.queryByText("admin.signed_in")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show older entries" }));
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "/api/v1/admin/audit?limit=50&action=user.banned&cursor=c2",
    );

    await user.clear(screen.getByLabelText("Exactly"));
    await user.click(screen.getByRole("button", { name: "Clear filter" }));
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/v1/admin/audit?limit=50");
    expect(screen.getByText("Nothing recorded yet.")).toBeInTheDocument();
  });
});
