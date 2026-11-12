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
    // The shortcuts arrive later; they are shown but can't be used yet.
    expect(screen.getByRole("button", { name: /Import resume/ })).toBeDisabled();

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

describe("step 4: a bit about you", () => {
  it("picks year, branch, days and hours, then finishes onto the describe page", async () => {
    render(
      <OnboardingFlow
        initial={progress({ display_name: "Aarav S." }, ["intents", "offers", "wants"])}
      />,
    );
    expect(screen.getByText("Step 4 of 4")).toBeVisible();
    await userEvent.click(screen.getByRole("radio", { name: "3rd" }));
    expect(screen.getByRole("radio", { name: "3rd" })).toHaveAttribute("aria-checked", "true");
    await userEvent.selectOptions(screen.getByLabelText("Branch"), "electronics");
    await userEvent.click(screen.getByRole("button", { name: "Saturday" }));
    await userEvent.click(screen.getByRole("radio", { name: "4–6" }));
    expect(screen.getByLabelText("Display name")).toHaveValue("Aarav S.");

    fetchMock.mockResolvedValueOnce(
      json(200, progress({}, ["intents", "offers", "wants", "about"])),
    );
    await userEvent.click(screen.getByRole("button", { name: /Finish/ }));
    expect(lastCall()).toMatchObject({
      url: "/api/v1/me/onboarding/about",
      body: {
        study_year: "3",
        branch: "electronics",
        available_days: ["sat"],
        weekly_hours: "4_6",
        display_name: "Aarav S.",
      },
    });
    expect(router.push).toHaveBeenCalledWith("/onboarding/describe");
  });

  it("leaves the name out when it is empty", async () => {
    render(<OnboardingFlow initial={progress({}, ["intents", "offers", "wants"])} />);
    fetchMock.mockResolvedValueOnce(
      json(200, progress({}, ["intents", "offers", "wants", "about"])),
    );
    await userEvent.click(screen.getByRole("button", { name: /Finish/ }));
    expect(lastCall().body).not.toHaveProperty("display_name");
  });
});
