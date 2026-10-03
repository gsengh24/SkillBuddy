import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ModerationReport } from "@/lib/api/schemas";

import { ReportReview, UnsuspendButton } from "./report-review";

const router = { push: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const REPORTED = "11111111-0000-4000-8000-000000000002";

const REPORT: ModerationReport = {
  id: "77777777-0000-4000-8000-000000000001",
  reason: "safety",
  details: "Felt threatened.",
  status: "open",
  reporter_id: "11111111-0000-4000-8000-000000000001",
  reported_id: REPORTED,
  reported_status: "active",
  connection_id: "55555555-0000-4000-8000-000000000001",
  target: "message",
  target_id: "66666666-0000-4000-8000-000000000002",
  messages: [
    {
      id: "66666666-0000-4000-8000-000000000001",
      label: null,
      sender: "reporter",
      body: "Can we meet?",
      sent_at: "2026-10-04T10:00:00Z",
    },
    {
      id: "66666666-0000-4000-8000-000000000002",
      label: null,
      sender: "reported",
      body: "You'll regret this",
      sent_at: "2026-10-04T10:01:00Z",
    },
  ],
  created_at: "2026-10-04T10:05:00Z",
  resolved_at: null,
  resolution_note: "",
};

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
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ReportReview", () => {
  it("shows the reason in plain words, the note and the copy, marking the reported message", () => {
    render(<ReportReview report={REPORT} />);
    expect(
      screen.getByText("Safety concern: threats, self-harm, or someone may be under 18"),
    ).toBeVisible();
    expect(screen.getByText("Felt threatened.")).toBeVisible();
    expect(screen.getByText("You'll regret this")).toBeVisible();
    expect(screen.getByText(/the reported message/)).toBeVisible();
    expect(screen.getByText("Reporter", { exact: true })).toBeVisible();
  });

  it("resolves with a note", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(200, { ...REPORT, status: "resolved" }));
    render(<ReportReview report={REPORT} />);

    await user.click(screen.getByRole("button", { name: "Resolve" }));
    expect(screen.getByText(/deleted 180 days later/)).toBeVisible();
    await user.type(screen.getByLabelText(/Note for your records/), "Warned them");
    await user.click(screen.getByRole("button", { name: "Resolve" }));

    expect(fetchMock.mock.calls[0]?.[0]).toBe(`/api/v1/moderation/reports/${REPORT.id}/resolve`);
    expect(JSON.parse((fetchMock.mock.calls[0]?.[1] as RequestInit).body as string)).toEqual({
      note: "Warned them",
    });
    expect(router.refresh).toHaveBeenCalled();
  });

  it("explains suspension, then suspends the reported account with the report attached", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(200, {
        user_id: REPORTED,
        status: "suspended",
        display_name: null,
        person: {
          user_id: REPORTED,
          display_name: null,
          links: null,
          summary: "",
          offers: [],
          seeks: [],
          interests: [],
          availability: "",
          languages: [],
        },
        suspended_at: null,
        note: "",
      }),
    );
    render(<ReportReview report={REPORT} />);

    await user.click(screen.getByRole("button", { name: "Suspend this account" }));
    expect(screen.getByText(/signed out at once and can't sign in/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Suspend" }));

    expect(fetchMock.mock.calls[0]?.[0]).toBe(`/api/v1/moderation/accounts/${REPORTED}/suspend`);
    expect(JSON.parse((fetchMock.mock.calls[0]?.[1] as RequestInit).body as string)).toEqual({
      note: "",
      report_id: REPORT.id,
    });
    expect(router.refresh).toHaveBeenCalled();
  });

  it("offers no suspend for an account already suspended or deleted, and no actions once resolved", () => {
    const { rerender } = render(
      <ReportReview report={{ ...REPORT, reported_status: "suspended" }} />,
    );
    expect(screen.getByText("Account suspended")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Suspend this account" })).not.toBeInTheDocument();

    rerender(<ReportReview report={{ ...REPORT, reported_id: null, reported_status: null }} />);
    expect(screen.getByText("Account deleted")).toBeVisible();

    rerender(
      <ReportReview
        report={{
          ...REPORT,
          status: "resolved",
          resolved_at: "2026-10-04T11:00:00Z",
          resolution_note: "Warned",
        }}
      />,
    );
    expect(screen.queryByRole("button", { name: "Resolve" })).not.toBeInTheDocument();
    expect(screen.getByText(/Warned/)).toBeVisible();
  });

  it("shows labelled parts for an intro report", () => {
    render(
      <ReportReview
        report={{
          ...REPORT,
          target: "intro",
          messages: [
            { id: null, label: "request", sender: "reported", body: "A designer", sent_at: null },
            { id: null, label: "note", sender: "reported", body: "Pay me", sent_at: null },
          ],
        }}
      />,
    );
    expect(screen.getByText("Intro")).toBeVisible();
    expect(screen.getByText("What they asked for")).toBeVisible();
    expect(screen.getByText("Their note")).toBeVisible();
  });

  it("shows API errors", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(409, {
        error: { code: "report_already_resolved", message: "x", request_id: null, details: null },
      }),
    );
    render(<ReportReview report={REPORT} />);
    await user.click(screen.getByRole("button", { name: "Resolve" }));
    await user.click(screen.getByRole("button", { name: "Resolve" }));
    expect(await screen.findByText("This report has already been resolved.")).toBeVisible();
  });
});

describe("UnsuspendButton", () => {
  it("confirms, then unsuspends", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(200, {}));
    render(<UnsuspendButton userId={REPORTED} />);
    await user.click(screen.getByRole("button", { name: "Unsuspend" }));
    expect(screen.getByText(/can sign in again/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Unsuspend" }));
    expect(fetchMock.mock.calls[0]?.[0]).toBe(`/api/v1/moderation/accounts/${REPORTED}/unsuspend`);
  });
});
