import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppealForm } from "@/components/auth/appeal-form";
import { ReportButton } from "@/components/safety/report-button";
import type { Case } from "@/lib/admin/schemas";

import { CaseDrawer } from "./safety";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

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
  router.refresh.mockReset();
  document.cookie = "csrf_token=csrf-value-123; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const messages = Array.from({ length: 7 }, (_, i) => ({
  id: `m${i}`,
  connection_id: "c1",
  sender_id: i % 2 ? "me" : "them",
  body: `line ${i}`,
  created_at: `2026-10-08T10:0${i}:00Z`,
}));

describe("ReportButton from a chat", () => {
  it("attaches up to 5 chosen messages and says only those are sent", async () => {
    fetchMock
      .mockResolvedValueOnce(json(200, { items: messages, next_cursor: null, retention_days: 90 }))
      .mockResolvedValueOnce(json(201, { id: "r1", created_at: "2026-10-08T10:10:00Z" }));
    const user = userEvent.setup({ delay: null });
    render(<ReportButton kind="profile" targetId="u2" attachFrom="c1" />);
    await user.click(screen.getByRole("button", { name: "Report" }));

    expect(screen.getByText(/Only the messages you tick are sent to our moderator/)).toBeVisible();
    const boxes = await screen.findAllByRole("checkbox");
    for (const box of boxes.slice(0, 5)) await user.click(box);
    expect(boxes[5]).toBeDisabled();
    await user.click(screen.getByRole("radio", { name: /Spam/ }));
    await user.click(screen.getByRole("button", { name: /Send report/ }));

    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toBe("/api/v1/people/u2/report");
    expect(JSON.parse(String(init.body)).message_ids).toHaveLength(5);
  });

  it("sends no messages when none are ticked", async () => {
    fetchMock
      .mockResolvedValueOnce(json(200, { items: messages, next_cursor: null, retention_days: 90 }))
      .mockResolvedValueOnce(json(201, { id: "r1", created_at: "2026-10-08T10:10:00Z" }));
    const user = userEvent.setup({ delay: null });
    render(<ReportButton kind="profile" targetId="u2" attachFrom="c1" />);
    await user.click(screen.getByRole("button", { name: "Report" }));
    await screen.findAllByRole("checkbox");
    await user.click(screen.getByRole("radio", { name: /Spam/ }));
    await user.click(screen.getByRole("button", { name: /Send report/ }));
    const [, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).not.toHaveProperty("message_ids");
  });
});

describe("AppealForm", () => {
  it("sends one appeal with its token", async () => {
    fetchMock.mockResolvedValueOnce(json(201, { created_at: "2026-10-08T10:00:00Z" }));
    const user = userEvent.setup({ delay: null });
    render(<AppealForm token="tok.sig" />);
    await user.type(screen.getByLabelText("Appeal this decision"), "It was a mistake.");
    await user.click(screen.getByRole("button", { name: "Send appeal" }));
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/appeals");
    expect(JSON.parse(String(init.body))).toEqual({
      token: "tok.sig",
      appeal: "It was a mistake.",
    });
    expect(screen.getByRole("status")).toHaveTextContent(/received your appeal/);
  });
});

const CASE: Case = {
  report: {
    id: "r1",
    status: "open",
    reason: "spam",
    target: "profile",
    created_at: "2026-10-08T10:00:00Z",
    decision: null,
    reported: { id: "u2", email: "asha@example.com", status: "active" },
    reporter: { id: "u1", email: "ravi@example.com", status: "active" },
  },
  details: "Keeps sending links.",
  attached: [{ label: null, sender: "reported", body: "<b>buy</b> my course", sent_at: null }],
  resolution_note: "",
  resolved_at: null,
  reported_history: { reports_against: 2 },
  reporter_history: { reports_filed: 1 },
};

describe("CaseDrawer", () => {
  it("shows what was attached as text and records a decision with a reason", async () => {
    fetchMock.mockResolvedValueOnce(
      json(200, { ...CASE.report, status: "resolved", decision: "warn" }),
    );
    const user = userEvent.setup({ delay: null });
    render(
      <CaseDrawer
        found={CASE}
        permissions={["view_users", "handle_reports"]}
        closeHref="/admin/reports"
      />,
    );
    expect(screen.getByText("<b>buy</b> my course")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Decide" }));
    const dialog = screen.getByRole("dialog", { name: "Decide this report" });
    await user.selectOptions(within(dialog).getByLabelText("Decision"), "warn");
    await user.type(within(dialog).getByLabelText(/Reason/), "First time, a warning is enough.");
    await user.click(within(dialog).getByRole("button", { name: "Record decision" }));
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/admin/safety/reports/r1/decide");
    expect(JSON.parse(String(init.body))).toEqual({
      decision: "warn",
      reason: "First time, a warning is enough.",
    });
  });

  it("offers no actions to read-only admins", () => {
    render(<CaseDrawer found={CASE} permissions={["view_users"]} closeHref="/admin/reports" />);
    expect(screen.queryByRole("group", { name: "Actions" })).not.toBeInTheDocument();
  });
});
