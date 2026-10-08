import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { InviteCode } from "@/lib/admin/schemas";

import { ApplicationActions, CreateCode, DomainList, ModeSwitch, RevokeCode } from "./access";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const REASON = "Pilot group for the autumn term";
const ACCESS = { mode: "closed", waitlist: 0, allowed_domains: [], blocked_domains: [] };
const CODE: InviteCode = {
  id: "c1",
  code: "CYN-FRIENDS",
  uses: 3,
  max_uses: 50,
  expires_at: null,
  revoked_at: null,
  created_at: "2026-10-01T10:00:00Z",
  created_by: "owner@example.com",
  status: "active",
};

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);
  router.refresh.mockReset();
  document.cookie = "csrf_token=csrf-value-123; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function sent(): { url: string; body: unknown } {
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  return { url, body: JSON.parse(String(init.body)) };
}

async function confirmWithReason(
  user: ReturnType<typeof userEvent.setup>,
  dialogName: string | RegExp,
  button: string,
) {
  const dialog = screen.getByRole("dialog", { name: dialogName });
  const confirm = within(dialog).getByRole("button", { name: button });
  await user.type(within(dialog).getByLabelText(/Reason/), "too short");
  expect(confirm).toBeDisabled();
  await user.clear(within(dialog).getByLabelText(/Reason/));
  await user.type(within(dialog).getByLabelText(/Reason/), REASON);
  await user.click(confirm);
}

describe("ModeSwitch", () => {
  it("shows the current mode and changes it only after a reason", async () => {
    fetchMock.mockResolvedValueOnce(json(200, ACCESS));
    const user = userEvent.setup({ delay: null });
    render(<ModeSwitch mode="open" />);
    expect(screen.getByRole("button", { name: "Open" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Anyone can sign up.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Closed" }));
    await confirmWithReason(user, "Change signup mode to Closed?", "Change mode");

    expect(sent()).toEqual({
      url: "/api/v1/admin/access/mode",
      body: { mode: "closed", reason: REASON },
    });
    expect(router.refresh).toHaveBeenCalled();
  });

  it("does nothing when the current mode is clicked", async () => {
    const user = userEvent.setup({ delay: null });
    render(<ModeSwitch mode="invite_only" />);
    await user.click(screen.getByRole("button", { name: "Invite only" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("ApplicationActions", () => {
  it("approves with a reason", async () => {
    const user = userEvent.setup({ delay: null });
    render(
      <ApplicationActions
        application={{
          id: "a1",
          email: "dev@example.com",
          source: "friend",
          created_at: "2026-10-01T10:00:00Z",
        }}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Approve" }));
    await confirmWithReason(user, "Approve dev@example.com?", "Approve");
    expect(sent()).toEqual({
      url: "/api/v1/admin/access/applications/a1/decide",
      body: { decision: "approve", reason: REASON },
    });
  });
});

describe("CreateCode", () => {
  it("sends the chosen code, limit and expiry", async () => {
    fetchMock.mockResolvedValueOnce(json(201, CODE));
    const user = userEvent.setup({ delay: null });
    render(<CreateCode />);
    await user.click(screen.getByRole("button", { name: "Create code" }));
    const dialog = screen.getByRole("dialog", { name: "Create an invite code" });
    await user.type(within(dialog).getByLabelText(/Code \(optional\)/), "cyn-friends");
    await user.clear(within(dialog).getByLabelText("Use limit"));
    await user.type(within(dialog).getByLabelText("Use limit"), "50");
    await user.clear(within(dialog).getByLabelText(/Expires in/));
    await confirmWithReason(user, "Create an invite code", "Create code");

    expect(sent()).toEqual({
      url: "/api/v1/admin/access/codes",
      body: { code: "cyn-friends", max_uses: 50, expires_in_days: null, reason: REASON },
    });
  });
});

describe("RevokeCode", () => {
  it("revokes after a reason", async () => {
    const user = userEvent.setup({ delay: null });
    render(<RevokeCode code={CODE} />);
    await user.click(screen.getByRole("button", { name: "Revoke" }));
    await confirmWithReason(user, "Revoke CYN-FRIENDS?", "Revoke");
    expect(sent()).toEqual({
      url: "/api/v1/admin/access/codes/c1/revoke",
      body: { reason: REASON },
    });
  });
});

describe("DomainList", () => {
  it("lists domains as plain text and removes one with a reason", async () => {
    const user = userEvent.setup({ delay: null });
    render(
      <DomainList
        kind="blocked"
        domains={["<b>bad</b>.example", "mailinator.com"]}
        placeholder="mailinator.com"
      />,
    );
    expect(screen.getByText("<b>bad</b>.example")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove mailinator.com" }));
    await confirmWithReason(user, /Remove mailinator\.com/, "Remove");
    expect(sent()).toEqual({
      url: "/api/v1/admin/access/domains/blocked/remove",
      body: { domain: "mailinator.com", reason: REASON },
    });
  });

  it("adds a domain with a reason", async () => {
    fetchMock.mockResolvedValueOnce(json(201, { domain: "example.edu" }));
    const user = userEvent.setup({ delay: null });
    render(<DomainList kind="allowed" domains={[]} placeholder="example.edu" />);
    expect(screen.getByText("None")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Add allowed domain"), "Example.edu");
    await user.click(screen.getByRole("button", { name: "Add" }));
    await confirmWithReason(user, /Add Example\.edu/, "Add");
    expect(sent()).toEqual({
      url: "/api/v1/admin/access/domains/allowed",
      body: { domain: "Example.edu", reason: REASON },
    });
  });
});
