import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { profileSchema, type Profile } from "@/lib/api/schemas";

import { UnderstandingReview } from "./understanding-review";
import { VisibilityToggle } from "./visibility-toggle";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const ABOUT = "I build React apps and want a designer for a small app, weekends.";
// Parsed, so the fields this test doesn't care about get the API's defaults.
const PROFILE: Profile = profileSchema.parse({
  user_id: "8d3f4b2a-0000-4000-8000-000000000001",
  display_name: "Ananya",
  about_text: ABOUT,
  links: [],
  timezone: "Asia/Kolkata",
  languages: ["en"],
  visibility: "matchable",
  email_notifications: true,
  parse_status: "parsed",
  parse_source: "template",
  understanding: {
    summary: "Builds React apps.",
    offers: ["React apps"],
    seeks: ["designer"],
    interests: ["chess"],
    availability: "weekends",
  },
  ai_consent_version: "2026-10-01",
  ai_consent_at: "2026-10-02T10:00:00Z",
  ai_consent_current: true,
  created_at: "2026-10-02T10:00:00Z",
  updated_at: "2026-10-02T10:00:00Z",
});

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
  router.push.mockReset();
  router.refresh.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function sentBody(call = 0): Record<string, unknown> {
  const init = fetchMock.mock.calls[call]?.[1] as RequestInit;
  return JSON.parse(init.body as string) as Record<string, unknown>;
}

describe("UnderstandingReview", () => {
  it("polls while the description is being read, then shows the result", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchMock.mockResolvedValueOnce(json(200, PROFILE));
    render(
      <UnderstandingReview
        initial={{ ...PROFILE, parse_status: "pending", understanding: null }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Reading your description…" })).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();
    await act(() => vi.advanceTimersByTimeAsync(2100));
    expect(await screen.findByText("designer")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/simple reader/)).toBeInTheDocument();
  });

  it("saves a correction", async () => {
    const user = userEvent.setup({ delay: null });
    const corrected = {
      ...PROFILE,
      parse_source: "user",
      understanding: { ...PROFILE.understanding!, seeks: ["UI designer", "mentor"] },
    };
    fetchMock.mockResolvedValueOnce(json(200, corrected));
    render(<UnderstandingReview initial={PROFILE} />);

    await user.click(screen.getByRole("button", { name: "Correct this" }));
    const seeks = screen.getByLabelText("You're looking for");
    await user.clear(seeks);
    await user.type(seeks, "UI designer, mentor");
    await user.click(screen.getByRole("button", { name: "Save corrections" }));

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/me/profile/understanding");
    expect(sentBody().seeks).toEqual(["UI designer", "mentor"]);
    expect(await screen.findByText("Edited by you.")).toBeInTheDocument();
    expect(screen.getByText("mentor")).toBeInTheDocument();
  });
});

describe("VisibilityToggle", () => {
  it("pauses and resumes matching with a PATCH", async () => {
    const user = userEvent.setup({ delay: null });
    fetchMock.mockResolvedValueOnce(json(200, { ...PROFILE, visibility: "paused" }));
    render(<VisibilityToggle initial="matchable" />);

    const toggle = screen.getByRole("switch", { name: /Show me in new matches/ });
    expect(toggle).toBeChecked();
    await user.click(toggle);

    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe("PATCH");
    expect(sentBody()).toEqual({ visibility: "paused" });
    expect(await screen.findByText(/won't be suggested to anyone new/)).toBeInTheDocument();
    expect(toggle).not.toBeChecked();
  });
});

describe("VisibilityToggle errors", () => {
  it("puts the switch back when the save fails", async () => {
    const user = userEvent.setup({ delay: null });
    fetchMock.mockResolvedValueOnce(apiError(503, "service_unavailable"));
    render(<VisibilityToggle initial="matchable" />);

    const toggle = screen.getByRole("switch", { name: /Show me in new matches/ });
    await user.click(toggle);

    expect(await screen.findByRole("alert")).toHaveTextContent(/temporarily unavailable/);
    expect(toggle).toBeChecked();
  });
});
