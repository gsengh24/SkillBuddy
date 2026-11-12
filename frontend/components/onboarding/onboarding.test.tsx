import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { onboardingSchema, type Onboarding } from "@/lib/api/schemas";

import { OnboardingFlow } from "./onboarding-flow";

const router = { push: vi.fn(), replace: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

type Step = "intents" | "offers" | "wants" | "about";
const ORDER: Step[] = ["intents", "offers", "wants", "about"];

function progress(over: Partial<Onboarding> = {}, saved: Step[] = []): Onboarding {
  const next = ORDER.find((step) => !saved.includes(step)) ?? "review";
  return onboardingSchema.parse({
    completed_at: null,
    next_step: next,
    steps: ORDER.map((step) => ({ step, state: saved.includes(step) ? "saved" : "todo" })),
    intents: [],
    offer_skills: [],
    want_skills: [],
    interest_tags: [],
    want_note: "",
    study_year: null,
    branch: null,
    available_days: [],
    weekly_hours: null,
    display_name: "",
    ...over,
  });
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;

function lastCall(): { url: string; method: string; body: unknown } {
  const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
  return {
    url,
    method: init.method ?? "GET",
    body: init.body ? JSON.parse(String(init.body)) : undefined,
  };
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  router.push.mockReset();
  window.history.replaceState(null, "", "/onboarding");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("step 1: what brings you here", () => {
  it("can't continue until an intent is picked, then saves and moves to step 2", async () => {
    fetchMock.mockResolvedValueOnce(
      json(200, progress({ intents: ["build_together", "mentor"] }, ["intents"])),
    );
    render(<OnboardingFlow initial={progress()} />);

    expect(screen.getByRole("heading", { level: 1, name: /What brings you here/ })).toBeVisible();
    expect(screen.getByText("Step 1 of 4")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Skip for now" })).toBeNull();
    const next = screen.getByRole("button", { name: /Continue/ });
    expect(next).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: /Build together/ }));
    await userEvent.click(screen.getByRole("button", { name: /Mentor/ }));
    expect(screen.getByRole("status")).toHaveTextContent("2 selected");
    expect(next).toBeEnabled();
    await userEvent.click(next);

    expect(lastCall()).toMatchObject({
      url: "/api/v1/me/onboarding/intents",
      method: "PUT",
      body: { intents: ["build_together", "mentor"] },
    });
    expect(
      await screen.findByRole("heading", { level: 1, name: /What are you good at/ }),
    ).toBeVisible();
    expect(window.location.search).toBe("?step=offers");
  });
});

describe("step 2: what you're good at", () => {
  it("picks chips, adds a typed skill, and saves them in order", async () => {
    render(<OnboardingFlow initial={progress({ intents: ["explore"] }, ["intents"])} />);
    expect(screen.getByText("Step 2 of 4")).toBeVisible();
    // "Skip the typing": both shortcuts are offered (screens 6 and 7).
    expect(screen.getByRole("button", { name: /Import resume/ })).toBeEnabled();
    expect(screen.getByText("Your file is read in your browser and isn't uploaded.")).toBeVisible();

    const coding = screen.getByRole("group", { name: "Coding" });
    await userEvent.click(within(coding).getByRole("button", { name: "React" }));
    await userEvent.click(within(coding).getByRole("button", { name: "Python" }));
    expect(within(coding).getByRole("button", { name: "React" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await userEvent.type(screen.getByRole("combobox", { name: "Search skills" }), "Django{Enter}");
    expect(
      within(screen.getByRole("group", { name: "Added" })).getByRole("button", { name: "Django" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("3 selected");

    fetchMock.mockResolvedValueOnce(
      json(200, progress({ offer_skills: ["React", "Python", "Django"] }, ["intents", "offers"])),
    );
    await userEvent.click(screen.getByRole("button", { name: /Continue/ }));
    expect(lastCall()).toMatchObject({
      url: "/api/v1/me/onboarding/offers",
      method: "PUT",
      body: { skills: ["React", "Python", "Django"] },
    });
    expect(
      await screen.findByRole("heading", { level: 1, name: /What are you looking for/ }),
    ).toBeVisible();
  });

  it("pastes text, keeps the chips confirmed, and saves them only on Continue", async () => {
    render(
      <OnboardingFlow
        initial={progress({ intents: ["explore"], offer_skills: ["Python"] }, ["intents"])}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Paste text" }));
    expect(
      screen.getByRole("heading", { level: 1, name: /Paste anything about you/ }),
    ).toBeVisible();
    await userEvent.type(
      screen.getByLabelText("Text about you"),
      "I build apps in React and Flutter. Weekend chess player.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Find my skills" }));
    expect(await screen.findByRole("heading", { level: 1, name: /We found these/ })).toBeVisible();
    // Drop Flutter: a dropped chip isn't used.
    await userEvent.click(screen.getByRole("button", { name: "Flutter" }));
    await userEvent.click(screen.getByRole("button", { name: /Use these/ }));

    // Back on step 2 with React added to Python; nothing has been saved yet.
    const coding = screen.getByRole("group", { name: "Coding" });
    expect(within(coding).getByRole("button", { name: "React" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(coding).getByRole("button", { name: "Flutter" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    const sent = fetchMock.mock.calls.map((call) => call as [string, RequestInit]);
    expect(sent.filter(([, init]) => init.method && init.method !== "GET")).toEqual([]);
    // The text itself never went anywhere.
    expect(sent.some(([url, init]) => `${url}${String(init.body)}`.includes("chess"))).toBe(false);

    fetchMock.mockResolvedValueOnce(
      json(200, progress({ offer_skills: ["Python", "React"] }, ["intents", "offers"])),
    );
    await userEvent.click(screen.getByRole("button", { name: /Continue/ }));
    expect(lastCall()).toMatchObject({
      url: "/api/v1/me/onboarding/offers",
      method: "PUT",
      body: { skills: ["Python", "React"] },
    });
    // The interest waits for step 3.
    expect(
      within(await screen.findByRole("group", { name: "Interests" })).getByRole("button", {
        name: "Chess",
      }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("goes back to step 2 from the shortcut without changing anything", async () => {
    render(<OnboardingFlow initial={progress({ intents: ["explore"] }, ["intents"])} />);
    await userEvent.click(screen.getByRole("button", { name: /Import resume/ }));
    expect(screen.getByRole("heading", { level: 1, name: /Import your resume/ })).toBeVisible();
    expect(
      screen.getByText("Up to 2 MB. Read in your browser, never uploaded or stored."),
    ).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Back to skills" }));
    expect(screen.getByRole("heading", { level: 1, name: /What are you good at/ })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("0 selected");
  });

  it("skips for now and keeps the step's state on the server", async () => {
    render(<OnboardingFlow initial={progress({}, ["intents"])} />);
    fetchMock.mockResolvedValueOnce(
      json(200, {
        ...progress({}, ["intents"]),
        next_step: "wants",
        steps: [
          { step: "intents", state: "saved" },
          { step: "offers", state: "skipped" },
          { step: "wants", state: "todo" },
          { step: "about", state: "todo" },
        ],
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Skip for now" }));
    expect(lastCall()).toMatchObject({ url: "/api/v1/me/onboarding/offers/skip", method: "POST" });
    expect(await screen.findByText("Step 3 of 4")).toBeVisible();
  });

  it("stays on the step and says what went wrong when a save fails", async () => {
    render(<OnboardingFlow initial={progress({}, ["intents"])} />);
    fetchMock.mockResolvedValueOnce(
      json(503, {
        error: {
          code: "storage_full",
          message: "Try again later.",
          request_id: "r",
          details: null,
        },
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: /Continue/ }));
    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.getByText("Step 2 of 4")).toBeVisible();
  });
});

describe("step 3: what you're looking for", () => {
  const initial = progress({ offer_skills: ["React", "Figma"] }, ["intents", "offers"]);

  it("shows pairings first as ink want chips, the exchange summary, and saves", async () => {
    render(<OnboardingFlow initial={initial} />);
    const pairs = screen.getByRole("region", { name: "Pairs well with what you offer" });
    await userEvent.click(within(pairs).getByRole("button", { name: "Node.js" }));

    // The summary is shown twice (phone and desktop placements); either shows the picks.
    const [summary] = screen.getAllByRole("region", { name: "Your exchange so far" });
    expect(within(summary!).getByText("React")).toBeVisible();
    expect(within(summary!).getByText("Node.js")).toBeInTheDocument();

    await userEvent.click(
      within(screen.getByRole("group", { name: "Interests" })).getByRole("button", {
        name: "Chess",
      }),
    );
    await userEvent.type(
      screen.getByLabelText("Anything specific? (optional)"),
      "a designer for my app",
    );
    expect(screen.getByText(/21 \/ 140/)).toBeVisible();

    fetchMock.mockResolvedValueOnce(json(200, progress({}, ["intents", "offers", "wants"])));
    await userEvent.click(screen.getByRole("button", { name: /Continue/ }));
    expect(lastCall()).toMatchObject({
      url: "/api/v1/me/onboarding/wants",
      body: { skills: ["Node.js"], interests: ["Chess"], note: "a designer for my app" },
    });
  });

  it("goes back to step 2 from the summary's Edit", async () => {
    render(<OnboardingFlow initial={initial} />);
    const [edit] = screen.getAllByRole("button", { name: "Edit" });
    await userEvent.click(edit!);
    expect(
      await screen.findByRole("heading", { level: 1, name: /What are you good at/ }),
    ).toBeVisible();
    // What was picked before is still picked.
    expect(screen.getAllByRole("button", { name: "React", pressed: true }).length).toBe(1);
  });
});

const PROFILE_OUT = {
  user_id: "u1",
  display_name: "",
  about_text: "Offers: React.",
  links: [],
  timezone: null,
  languages: [],
  visibility: "matchable",
  parse_status: "pending",
  parse_source: "template",
  understanding: null,
  ai_consent_version: "v1",
  ai_consent_at: "2026-11-12T10:00:00Z",
  ai_consent_current: true,
  created_at: "2026-11-12T10:00:00Z",
  updated_at: "2026-11-12T10:00:00Z",
};

describe("step 4: a bit about you", () => {
  const ready = progress({ display_name: "Aarav S." }, ["intents", "offers", "wants"]);

  it("needs the AI consent line before finishing, then saves, finishes and goes to step 5", async () => {
    render(<OnboardingFlow initial={ready} />);
    expect(screen.getByText("Step 4 of 4")).toBeVisible();
    await userEvent.click(screen.getByRole("radio", { name: "3rd" }));
    expect(screen.getByRole("radio", { name: "3rd" })).toHaveAttribute("aria-checked", "true");
    await userEvent.selectOptions(screen.getByLabelText("Branch"), "electronics");
    await userEvent.click(screen.getByRole("button", { name: "Saturday" }));
    await userEvent.click(screen.getByRole("radio", { name: "4–6" }));
    expect(screen.getByLabelText("Display name")).toHaveValue("Aarav S.");

    // The consent line is unchanged and required: nothing is sent without it.
    await userEvent.click(screen.getByRole("button", { name: /Finish/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/agree to how AI/);
    expect(fetchMock).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("checkbox", { name: /read by AI to find and explain/ }));

    fetchMock
      .mockResolvedValueOnce(json(200, progress({}, ["intents", "offers", "wants", "about"])))
      .mockResolvedValueOnce(json(200, PROFILE_OUT));
    await userEvent.click(screen.getByRole("button", { name: /Finish/ }));
    const [aboutUrl, aboutInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(aboutUrl).toBe("/api/v1/me/onboarding/about");
    expect(JSON.parse(String(aboutInit.body))).toEqual({
      study_year: "3",
      branch: "electronics",
      available_days: ["sat"],
      weekly_hours: "4_6",
      display_name: "Aarav S.",
    });
    expect(lastCall()).toMatchObject({
      url: "/api/v1/me/onboarding/finish",
      method: "POST",
      body: { ai_consent: true },
    });
    expect(router.push).toHaveBeenCalledWith("/onboarding/review");
  });

  it("skips step 4 and still finishes, without asking again when consent is current", async () => {
    render(<OnboardingFlow initial={ready} needsConsent={false} />);
    expect(screen.queryByRole("checkbox", { name: /read by AI/ })).toBeNull();
    fetchMock
      .mockResolvedValueOnce(json(200, progress({}, ["intents", "offers", "wants"])))
      .mockResolvedValueOnce(json(200, PROFILE_OUT));
    await userEvent.click(screen.getByRole("button", { name: "Skip for now" }));
    expect((fetchMock.mock.calls[0] as [string])[0]).toBe("/api/v1/me/onboarding/about/skip");
    expect(lastCall()).toMatchObject({
      url: "/api/v1/me/onboarding/finish",
      body: { ai_consent: false },
    });
    expect(router.push).toHaveBeenCalledWith("/onboarding/review");
  });

  it("leaves the name out when it is empty", async () => {
    render(
      <OnboardingFlow
        initial={progress({}, ["intents", "offers", "wants"])}
        needsConsent={false}
      />,
    );
    fetchMock
      .mockResolvedValueOnce(json(200, progress({}, ["intents", "offers", "wants", "about"])))
      .mockResolvedValueOnce(json(200, PROFILE_OUT));
    await userEvent.click(screen.getByRole("button", { name: /Finish/ }));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).not.toHaveProperty("display_name");
  });
});
