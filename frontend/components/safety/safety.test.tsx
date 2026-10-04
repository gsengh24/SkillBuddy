import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BlockButton, UnblockButton } from "./block-button";
import { ReportButton } from "./report-button";

const router = { push: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const THEM = "11111111-0000-4000-8000-000000000002";

function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const BLOCKED = {
  user_id: THEM,
  created_at: "2026-10-04T10:00:00Z",
  person: {
    user_id: THEM,
    display_name: null,
    links: null,
    summary: "",
    offers: [],
    seeks: [],
    interests: [],
    availability: "",
    languages: [],
  },
};

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  router.push.mockReset();
  router.refresh.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("BlockButton", () => {
  it("explains what blocking does before doing it", async () => {
    const user = userEvent.setup();
    render(<BlockButton userId={THEM} name="Asha" />);

    await user.click(screen.getByRole("button", { name: "Block" }));

    expect(screen.getByText("Block Asha?")).toBeVisible();
    expect(screen.getByText(/your chat closes for both of you/)).toBeVisible();
    expect(screen.getByText(/They won't be told/)).toBeVisible();
    expect(
      screen.getByText(/to talk again, one of you would need to send a new intro/),
    ).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("blocks and goes where it was told", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(201, BLOCKED));
    render(<BlockButton userId={THEM} name="Asha" redirectTo="/messages" />);

    await user.click(screen.getByRole("button", { name: "Block" }));
    await user.click(screen.getByRole("button", { name: "Block" }));

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/blocks");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ user_id: THEM });
    expect(router.push).toHaveBeenCalledWith("/messages");
    expect(router.refresh).toHaveBeenCalled();
  });

  it("can be cancelled", async () => {
    const user = userEvent.setup();
    render(<BlockButton userId={THEM} name="Asha" />);
    await user.click(screen.getByRole("button", { name: "Block" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Block Asha?")).not.toBeInTheDocument();
  });

  it("shows API errors", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(429, { error: { code: "rate_limited", message: "x", request_id: null, details: null } }),
    );
    render(<BlockButton userId={THEM} name="Asha" />);
    await user.click(screen.getByRole("button", { name: "Block" }));
    await user.click(screen.getByRole("button", { name: "Block" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many attempts");
    expect(router.refresh).not.toHaveBeenCalled();
  });
});

describe("UnblockButton", () => {
  it("says the chat stays closed, then unblocks", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(204));
    render(<UnblockButton userId={THEM} />);

    await user.click(screen.getByRole("button", { name: "Unblock" }));
    expect(screen.getByText(/Your old chat stays closed/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Unblock" }));

    expect(fetchMock.mock.calls[0]?.[0]).toBe(`/api/v1/blocks/${THEM}`);
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe("DELETE");
    expect(router.refresh).toHaveBeenCalled();
  });
});

describe("ReportButton", () => {
  it("says what the moderator will see and needs a reason", async () => {
    const user = userEvent.setup();
    render(<ReportButton kind="message" targetId="m1" />);

    await user.click(screen.getByRole("button", { name: "Report" }));

    expect(screen.getByText(/this message and the 10 messages before it/)).toBeVisible();
    expect(screen.getByText(/won't be told who reported them/)).toBeVisible();
    expect(screen.getByRole("radio", { name: "Harassment or bullying" })).toBeInTheDocument();
    expect(
      screen.getByRole("radio", {
        name: "Safety concern: threats, self-harm, or someone may be under 18",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(6);
    expect(screen.getByRole("button", { name: "Send report" })).toBeDisabled();
  });

  it.each([
    ["message", "m1", "/api/v1/messages/m1/report"],
    ["intro", "i1", "/api/v1/intros/i1/report"],
    ["profile", THEM, `/api/v1/people/${THEM}/report`],
    ["goal", "g1", "/api/v1/space-goals/g1/report"],
    ["note", "l1", "/api/v1/progress-logs/l1/report"],
  ] as const)("sends a %s report and then offers to block", async (kind, id, path) => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(201, { id: "r1", created_at: "2026-10-04T10:00:00Z" }));
    render(<ReportButton kind={kind} targetId={id} blockUserId={THEM} blockName="Asha" />);

    await user.click(screen.getByRole("button", { name: "Report" }));
    await user.click(screen.getByRole("radio", { name: "Scam or asking for money" }));
    await user.type(screen.getByLabelText(/Anything else/), "  Asked for money  ");
    await user.click(screen.getByRole("button", { name: "Send report" }));

    expect(fetchMock.mock.calls[0]?.[0]).toBe(path);
    expect(JSON.parse((fetchMock.mock.calls[0]?.[1] as RequestInit).body as string)).toEqual({
      reason: "scam",
      details: "Asked for money",
    });
    expect(await screen.findByRole("status")).toHaveTextContent("received your report");
    expect(screen.getByRole("button", { name: "Block" })).toBeInTheDocument();
  });

  it("shows API errors", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(409, {
        error: { code: "already_reported", message: "x", request_id: null, details: null },
      }),
    );
    render(<ReportButton kind="intro" targetId="i1" />);
    await user.click(screen.getByRole("button", { name: "Report" }));
    await user.click(screen.getByRole("radio", { name: "Spam or advertising" }));
    await user.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByText(/already reported this/)).toBeVisible();
  });
});
