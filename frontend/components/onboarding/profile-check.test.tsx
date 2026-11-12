import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { profileSchema, type Profile } from "@/lib/api/schemas";

import {
  MAX_POLLS,
  POLL_MS,
  ProfileCheck,
  cardAvailability,
  cardMeta,
  cardTitle,
} from "./profile-check";

const router = { push: vi.fn(), replace: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const TEMPLATE = "Offers: React, Figma. Wants: Node.js. Into: chess. Free: Weekends · 4-6 h/week.";

function profile(over: Partial<Profile> = {}): Profile {
  return profileSchema.parse({
    user_id: "8d3f4b2a-0000-4000-8000-000000000001",
    display_name: "Aarav S.",
    about_text: TEMPLATE,
    links: [],
    timezone: null,
    languages: [],
    visibility: "matchable",
    intents: ["build_together", "skill_exchange"],
    offer_skills: ["React", "Figma"],
    want_skills: ["Node.js"],
    interest_tags: ["Chess"],
    study_year: "2",
    branch: "computer",
    available_days: ["sat", "sun"],
    weekly_hours: "4_6",
    onboarding_completed_at: null,
    parse_status: "pending",
    parse_source: "template",
    understanding: null,
    ai_consent_version: "v1",
    ai_consent_at: "2026-11-12T10:00:00Z",
    ai_consent_current: true,
    created_at: "2026-11-12T10:00:00Z",
    updated_at: "2026-11-12T10:00:00Z",
    ...over,
  });
}

const READY = profile({
  parse_status: "parsed",
  parse_source: "llm",
  about_text: "I build React front ends and design in Figma; keen to learn Node.js.",
  understanding: {
    title: "Frontend builder looking for a backend partner",
    summary: "Builds React front ends and designs in Figma. Wants a Node.js partner.",
    offers: ["React", "Figma"],
    seeks: ["Node.js"],
    interests: ["Chess"],
    availability: "Weekends · 4-6 h/week",
  },
});

const FALLBACK = profile({
  parse_status: "parsed",
  parse_source: "template",
  understanding: {
    title: "Offers React, wants Node.js",
    summary: "Offers React and Figma.",
    offers: ["React", "Figma"],
    seeks: ["Node.js"],
    interests: ["Chess"],
    availability: "Weekends · 4-6 h/week",
  },
});

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
  router.push.mockReset();
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function card() {
  return screen.getByRole("article", { name: "Preview of your match card" });
}

describe("step 5: check what we understood", () => {
  it("shows the loading card while the AI writes, then the ready card", async () => {
    fetchMock.mockResolvedValueOnce(json(200, profile())).mockResolvedValueOnce(json(200, READY));
    render(<ProfileCheck />);

    expect(screen.getByRole("heading", { level: 1, name: /how others/ })).toBeVisible();
    expect(screen.getByRole("article", { name: "Your match card is loading" })).toBeVisible();
    await act(() => vi.advanceTimersByTimeAsync(10));
    // Still being written: the skeleton stays, and the template text is already there.
    expect(screen.getByText(/Reading your profile/)).toBeVisible();
    expect(screen.getByLabelText("About you")).toHaveValue(TEMPLATE);

    await act(() => vi.advanceTimersByTimeAsync(POLL_MS + 10));
    const preview = card();
    expect(
      within(preview).getByRole("heading", {
        name: "Frontend builder looking for a backend partner",
      }),
    ).toBeVisible();
    expect(within(preview).getByText(/Wants a Node.js partner/)).toBeVisible();
    expect(within(preview).getByText("2nd year · Computer Engineering")).toBeVisible();
    expect(within(preview).getByText("Build together")).toBeVisible();
    expect(within(preview).getByText("Why you match")).toBeVisible();
    // The AI's text replaces the template while it hasn't been changed.
    expect(screen.getByLabelText("About you")).toHaveValue(READY.about_text);
    // Content rules: no name on the card.
    expect(within(preview).queryByText(/Aarav/)).toBeNull();
    expect(screen.queryByText(/polish this shortly/)).toBeNull();
  });

  it("shows the fallback card with the muted note when the template was used", async () => {
    fetchMock.mockResolvedValueOnce(json(200, FALLBACK));
    render(<ProfileCheck />);
    await act(() => vi.advanceTimersByTimeAsync(10));
    const preview = card();
    expect(
      within(preview).getByRole("heading", { name: "Offers React, wants Node.js" }),
    ).toBeVisible();
    // No sentence on the fallback card, and no error.
    expect(within(preview).queryByText("Offers React and Figma.")).toBeNull();
    expect(within(preview).getByText("We'll polish this shortly.")).toBeVisible();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("falls back to the template after waiting, never to an error", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(json(200, profile())));
    render(<ProfileCheck />);
    for (let i = 0; i <= MAX_POLLS; i++) {
      await act(() => vi.advanceTimersByTimeAsync(POLL_MS + 10));
    }
    expect(fetchMock).toHaveBeenCalledTimes(MAX_POLLS);
    expect(within(card()).getByRole("heading", { name: "Offers React and Figma" })).toBeVisible();
    expect(screen.getByText("We'll polish this shortly.")).toBeVisible();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("keeps an edited text, then finishes onboarding with it and goes Home", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    fetchMock.mockResolvedValueOnce(json(200, FALLBACK));
    render(<ProfileCheck />);
    await act(() => vi.advanceTimersByTimeAsync(10));

    const about = screen.getByLabelText("About you");
    await user.clear(about);
    await user.type(about, "I make React apps.");
    expect(screen.getByText("18/500")).toBeInTheDocument();

    fetchMock.mockResolvedValueOnce(json(200, { ...FALLBACK, onboarding_completed_at: "now" }));
    await user.click(screen.getByRole("button", { name: /Looks good/ }));
    const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
    expect(url).toBe("/api/v1/me/onboarding/complete");
    expect(JSON.parse(String(init.body))).toEqual({ about_text: "I make React apps." });
    expect(router.push).toHaveBeenCalledWith("/home");
  });

  it("goes back to the steps with Edit", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    fetchMock.mockResolvedValueOnce(json(200, FALLBACK));
    render(<ProfileCheck />);
    await act(() => vi.advanceTimersByTimeAsync(10));
    await user.click(screen.getByRole("button", { name: "Edit" }));
    expect(router.push).toHaveBeenCalledWith("/onboarding?step=offers");
  });
});

describe("card text", () => {
  it("builds the heading, year and availability from the picks", () => {
    const bare = profile({ want_skills: [], offer_skills: ["React", "Flutter", "Figma", "SQL"] });
    expect(cardTitle(bare)).toBe("Offers React, Flutter and Figma");
    expect(cardTitle(profile({ offer_skills: [], want_skills: ["Node.js"] }))).toBe(
      "Looking for Node.js",
    );
    expect(cardTitle(profile({ offer_skills: [], want_skills: [] }))).toBe("New here");
    expect(cardMeta(profile({ study_year: "postgrad", branch: null }))).toBe("Postgrad");
    expect(cardAvailability(profile())).toBe("Weekends · 4–6 h/week");
    expect(cardAvailability(profile({ available_days: ["mon", "wed"], weekly_hours: null }))).toBe(
      "Mon, Wed",
    );
  });
});
