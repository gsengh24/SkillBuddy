import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Match, MatchRequest } from "@/lib/api/schemas";

import { MatchCard } from "./match-card";
import { RequestCard } from "./request-card";
import { RequestComposer } from "./request-composer";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const REQUEST: MatchRequest = {
  id: "11111111-0000-4000-8000-000000000001",
  text: "A designer for my budgeting app.",
  requested_intent: "build_together",
  intent: null,
  status: "pending",
  match_count: 0,
  created_at: "2026-10-03T10:00:00Z",
  matched_at: null,
  expires_at: "2026-11-02T10:00:00Z",
};
const MATCH: Match = {
  id: "22222222-0000-4000-8000-000000000001",
  rank: 1,
  reason: "They offer UI design, which you are looking for.",
  status: "shown",
  candidate: {
    user_id: "33333333-0000-4000-8000-000000000001",
    summary: "Final-year design student.",
    offers: ["UI design", "Figma"],
    seeks: ["a developer"],
    interests: ["chess"],
    availability: "weekends",
    languages: ["en"],
  },
};

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function apiError(status: number, code: string) {
  return json(status, { error: { code, message: "Server.", request_id: "r1", details: null } });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  router.refresh.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("RequestComposer", () => {
  it("sends the text and the chosen intent, then refreshes the list", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(202, REQUEST));
    render(<RequestComposer />);

    const chip = screen.getByRole("button", { name: /Build together/ });
    await user.click(chip);
    expect(chip).toHaveAttribute("aria-pressed", "true");
    await user.type(screen.getByLabelText("Describe it in your own words"), REQUEST.text);
    await user.click(screen.getByRole("button", { name: "Find matches" }));

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/requests");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      text: REQUEST.text,
      intent: "build_together",
    });
    expect(router.refresh).toHaveBeenCalled();
  });

  it("asks for more text before calling the API, and shows API errors", async () => {
    const user = userEvent.setup();
    render(<RequestComposer />);
    await user.type(screen.getByLabelText("Describe it in your own words"), "hi");
    await user.click(screen.getByRole("button", { name: "Find matches" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/at least 10 characters/);
    expect(fetchMock).not.toHaveBeenCalled();

    fetchMock.mockResolvedValueOnce(apiError(409, "too_many_open_requests"));
    await user.type(screen.getByLabelText("Describe it in your own words"), " and much more text");
    await user.click(screen.getByRole("button", { name: "Find matches" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Close one to start another/);
  });
});

describe("RequestCard", () => {
  it("polls while pending, then shows the matches", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchMock
      .mockResolvedValueOnce(json(200, { ...REQUEST, status: "ready", match_count: 1 }))
      .mockResolvedValueOnce(json(200, { items: [MATCH] }));
    render(<RequestCard initial={REQUEST} />);

    expect(screen.getByText("Finding people for this…")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(3100));
    expect(await screen.findByText("Final-year design student.")).toBeInTheDocument();
    // No heading from the matcher yet: a plain one, with their words below it.
    expect(screen.getByRole("heading", { name: "Your request" })).toBeInTheDocument();
    expect(screen.getByText(`“${REQUEST.text}”`)).toBeInTheDocument();
    expect(fetchMock.mock.calls[0]?.[0]).toBe(`/api/v1/requests/${REQUEST.id}`);
    expect(fetchMock.mock.calls[1]?.[0]).toBe(`/api/v1/requests/${REQUEST.id}/matches`);
    expect(screen.getByText("1 match ready.")).toBeInTheDocument();
  });

  it("is headed by the matcher's wording, not the person's", async () => {
    fetchMock.mockResolvedValueOnce(json(200, { items: [] }));
    render(
      <RequestCard
        initial={{ ...REQUEST, status: "ready", title: "Designer for a budgeting app" }}
      />,
    );
    expect(
      await screen.findByRole("heading", { name: "Designer for a budgeting app" }),
    ).toBeInTheDocument();
    expect(screen.getByText(`“${REQUEST.text}”`)).toBeInTheDocument();
  });

  it("says when nobody fits yet", async () => {
    fetchMock.mockResolvedValueOnce(json(200, { items: [] }));
    render(<RequestCard initial={{ ...REQUEST, status: "ready" }} />);
    expect(await screen.findByText(/Nobody fits yet/)).toBeInTheDocument();
  });

  it("closes a request", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(json(200, { items: [] }))
      .mockResolvedValueOnce(json(200, { ...REQUEST, status: "closed" }));
    render(<RequestCard initial={{ ...REQUEST, status: "ready" }} />);
    await user.click(await screen.findByRole("button", { name: "Close this request" }));
    expect(await screen.findByText("Closed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Close this request" })).not.toBeInTheDocument();
  });
});

describe("MatchCard", () => {
  it("uses the matcher's heading and tidies older tags", () => {
    render(
      <MatchCard
        match={{
          ...MATCH,
          candidate: {
            ...MATCH.candidate,
            title: "UI designer and illustrator",
            offers: ["ui design skills", "Figma"],
            interests: ["figma", "chess"],
          },
        }}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "UI designer and illustrator" }),
    ).toBeInTheDocument();
    expect(screen.getByText("UI design")).toBeInTheDocument();
    expect(screen.getAllByText(/^figma$/i)).toHaveLength(1);
    expect(screen.getByText("Chess")).toBeInTheDocument();
  });

  it("shows what they offer and why, but no name", () => {
    render(<MatchCard match={MATCH} />);
    // The heading is a short label; the sentence about them is body text.
    expect(screen.getByRole("heading", { name: "UI design · Figma" })).toBeInTheDocument();
    expect(screen.getByText("Final-year design student.")).toBeInTheDocument();
    expect(screen.getByText("Can help with")).toBeInTheDocument();
    expect(screen.getByText("UI design")).toBeInTheDocument();
    expect(screen.getByText("Available weekends")).toBeInTheDocument();
    expect(screen.getByText("Why this match")).toBeInTheDocument();
    expect(screen.getByText(MATCH.reason)).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send intro" })).toBeEnabled();
  });
});
