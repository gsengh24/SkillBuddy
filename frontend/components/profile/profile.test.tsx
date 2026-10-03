import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Profile } from "@/lib/api/schemas";
import { profileCompleteness } from "@/lib/profile/limits";

import { ProfileForm } from "./profile-form";
import { UnderstandingReview } from "./understanding-review";
import { VisibilityToggle } from "./visibility-toggle";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const ABOUT = "I build React apps and want a designer for a small app, weekends.";
const PROFILE: Profile = {
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

describe("ProfileForm", () => {
  it("shows the AI consent line and requires it on the first save", async () => {
    const user = userEvent.setup();
    render(<ProfileForm profile={null} mode="onboarding" />);

    expect(screen.getByText(/read by AI to find and explain your matches/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "How we use AI" })).toHaveAttribute(
      "href",
      "/privacy#ai",
    );
    await user.type(screen.getByLabelText("Your name"), "Ananya");
    await user.type(screen.getByLabelText("About you"), ABOUT);
    await user.click(screen.getByRole("button", { name: "Save and continue" }));

    expect(screen.getByRole("alert")).toHaveTextContent(/agree to how AI is used/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("checks length and links before calling the API", async () => {
    const user = userEvent.setup();
    render(<ProfileForm profile={null} mode="onboarding" />);
    await user.type(screen.getByLabelText("Your name"), "Ananya");
    await user.type(screen.getByLabelText("About you"), "Too short");
    await user.click(screen.getByRole("button", { name: "Save and continue" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/at least 20 characters/);

    await user.type(screen.getByLabelText("About you"), " but now it is long enough.");
    await user.type(screen.getByLabelText("Link 1"), "http://insecure.example.com");
    await user.click(screen.getByRole("button", { name: "Save and continue" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/https:\/\//);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("saves with consent, then goes to the review step", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(200, { ...PROFILE, parse_status: "pending" }));
    render(<ProfileForm profile={null} mode="onboarding" />);

    await user.type(screen.getByLabelText("Your name"), "Ananya");
    await user.type(screen.getByLabelText("About you"), ABOUT);
    await user.type(screen.getByLabelText("Link 1"), "https://github.com/ananya");
    await user.click(screen.getByRole("checkbox", { name: "Hindi" }));
    await user.click(screen.getByRole("checkbox", { name: /read by AI/ }));
    await user.click(screen.getByRole("button", { name: "Save and continue" }));

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/me/profile");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe("PUT");
    expect(sentBody()).toMatchObject({
      display_name: "Ananya",
      about_text: ABOUT,
      links: ["https://github.com/ananya"],
      languages: ["hi"],
      ai_consent: true,
      visibility: "matchable",
    });
    expect(router.push).toHaveBeenCalledWith("/profile?welcome=1");
  });

  it("does not ask again while consent is current, and shows API errors", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(apiError(429, "rate_limited"));
    render(<ProfileForm profile={PROFILE} mode="edit" />);

    expect(screen.queryByText(/read by AI to find/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(sentBody().ai_consent).toBe(false);
    expect(await screen.findByRole("alert")).toHaveTextContent(/Too many attempts/);
  });

  it("asks again when the consent version changed", () => {
    render(<ProfileForm profile={{ ...PROFILE, ai_consent_current: false }} mode="edit" />);
    expect(screen.getByRole("checkbox", { name: /read by AI/ })).not.toBeChecked();
  });
});

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
    const user = userEvent.setup();
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
    const user = userEvent.setup();
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
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(apiError(503, "service_unavailable"));
    render(<VisibilityToggle initial="matchable" />);

    const toggle = screen.getByRole("switch", { name: /Show me in new matches/ });
    await user.click(toggle);

    expect(await screen.findByRole("alert")).toHaveTextContent(/temporarily unavailable/);
    expect(toggle).toBeChecked();
  });
});

describe("profileCompleteness", () => {
  it("scores what is filled in", () => {
    expect(profileCompleteness(null)).toBeNull();
    expect(profileCompleteness({ ...PROFILE, parse_status: "pending", languages: [] })).toBe(60);
    expect(profileCompleteness({ ...PROFILE, links: ["https://x.dev"] })).toBe(100);
  });
});
