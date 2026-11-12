import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FinishProfile } from "@/components/home/finish-profile";
import { NudgeCard } from "@/components/home/nudge-card";
import { onboardingSchema, type Onboarding } from "@/lib/api/schemas";

import { useSkillGate } from "./skill-gate";

const router = { push: vi.fn(), replace: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function progress(over: Partial<Onboarding> = {}): Onboarding {
  return onboardingSchema.parse({
    completed_at: null,
    next_step: "offers",
    steps: [
      { step: "intents", state: "saved" },
      { step: "offers", state: "todo" },
      { step: "wants", state: "skipped" },
      { step: "about", state: "todo" },
    ],
    intents: ["build_together"],
    offer_skills: ["React"],
    want_skills: [],
    interest_tags: [],
    want_note: "",
    study_year: null,
    branch: null,
    available_days: [],
    weekly_hours: null,
    display_name: "",
    strength: { percent: 14, done: 1, total: 7, missing: ["offers"] },
    ...over,
  });
}

const PROFILE = {
  user_id: "u1",
  display_name: "Ravi",
  about_text: "Offers: React.",
  links: [],
  timezone: null,
  languages: [],
  visibility: "matchable",
  parse_status: "parsed",
  parse_source: "template",
  understanding: null,
  ai_consent_version: "v1",
  ai_consent_at: null,
  ai_consent_current: true,
  created_at: "2026-11-12T10:00:00Z",
  updated_at: "2026-11-12T10:00:00Z",
};

let fetchMock: ReturnType<typeof vi.fn>;

function calls(): { url: string; method: string; body: unknown }[] {
  return fetchMock.mock.calls.map((call) => {
    const [url, init] = call as [string, RequestInit];
    return {
      url,
      method: init.method ?? "GET",
      body: init.body ? JSON.parse(String(init.body)) : undefined,
    };
  });
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  router.push.mockReset();
  router.refresh.mockReset();
  document.cookie = "csrf_token=csrf-value-123; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Finish your profile (screen 8)", () => {
  it("shows the API's strength, the steps left and one way on", () => {
    render(<FinishProfile progress={progress()} demand={{ skill: "React", count: 23 }} />);
    const panel = screen.getByRole("region", { name: /Finish your profile/ });
    expect(within(panel).getByRole("meter", { name: "Profile strength" })).toHaveAttribute(
      "aria-valuenow",
      "14",
    );
    const steps = within(panel).getByRole("list", { name: "Steps" });
    expect(within(steps).getByText(/What brings you here/)).toHaveTextContent("done");
    // A skipped step still counts as left to do.
    expect(within(panel).getByText("3 quick steps left")).toBeVisible();
    expect(within(panel).getByRole("link", { name: "Finish in 60 seconds" })).toHaveAttribute(
      "href",
      "/onboarding",
    );
    // Aggregate only: a number and a skill, no names.
    expect(screen.getByText(/are looking for React skills this week/)).toHaveTextContent(
      "23 people",
    );
  });

  it("hides the social-proof line when the API withholds the count", () => {
    render(<FinishProfile progress={progress()} demand={null} />);
    expect(screen.queryByText(/are looking for/)).toBeNull();
  });
});

describe("in-context nudge (screen 11)", () => {
  it("adds the team's skill in one tap and doesn't come back", async () => {
    fetchMock
      .mockResolvedValueOnce(json(200, PROFILE))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    render(
      <NudgeCard
        nudge={{ kind: "team_skill", skill: "Machine learning", team_id: "t1", team_name: "ML" }}
        offerSkills={["React"]}
      />,
    );
    expect(screen.getByRole("region", { name: "Suggestion" })).toHaveTextContent(
      "You joined ML. Add Machine learning to your skills?",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(calls()).toEqual([
      {
        url: "/api/v1/me/profile",
        method: "PATCH",
        body: { offer_skills: ["React", "Machine learning"] },
      },
      { url: "/api/v1/me/nudges/team_skill/dismiss", method: "POST", body: undefined },
    ]);
    expect(await screen.findByRole("status")).toHaveTextContent("Added Machine learning");
  });

  it("dismisses for good from Dismiss or the ✕", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    render(
      <NudgeCard
        nudge={{ kind: "availability", skill: null, team_id: null, team_name: null }}
        offerSkills={[]}
      />,
    );
    expect(screen.getByText(/Add your availability/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Dismiss suggestion" }));
    expect(screen.queryByRole("region", { name: "Suggestion" })).toBeNull();
    expect(calls()[0]).toMatchObject({ url: "/api/v1/me/nudges/availability/dismiss" });
  });

  it("opens the availability section from Add availability", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    render(
      <NudgeCard
        nudge={{ kind: "availability", skill: null, team_id: null, team_name: null }}
        offerSkills={[]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Add availability" }));
    expect(router.push).toHaveBeenCalledWith("/you#s-avail");
  });

  it("shows nothing for a kind it doesn't know", () => {
    const { container } = render(
      <NudgeCard
        nudge={{ kind: "new_kind", skill: null, team_id: null, team_name: null }}
        offerSkills={[]}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

function GatedSend({ onDone }: { onDone: (result: unknown) => void }) {
  const { guard, dialog } = useSkillGate();
  return (
    <>
      <button
        type="button"
        onClick={async () =>
          onDone(
            await guard(async () => {
              const response = await fetch("/api/v1/matches/m1/intro", { method: "POST" });
              if (!response.ok) {
                const { ApiError } = await import("@/lib/api/errors");
                throw new ApiError(response.status, await response.json(), undefined);
              }
              return "sent";
            }),
          )
        }
      >
        Send intro
      </button>
      {dialog}
    </>
  );
}

const SKILLS_REQUIRED = {
  error: { code: "skills_required", message: "Add 3 skills.", request_id: "r", details: null },
};

describe("soft gate (screen 9)", () => {
  it("asks for 3 skills, saves them and carries on with the intro", async () => {
    const done = vi.fn();
    fetchMock
      .mockResolvedValueOnce(json(409, SKILLS_REQUIRED))
      .mockResolvedValueOnce(json(200, progress()))
      .mockResolvedValueOnce(json(200, progress({ offer_skills: ["React", "Figma", "Python"] })))
      .mockResolvedValueOnce(json(201, {}));
    render(<GatedSend onDone={done} />);
    const opener = screen.getByRole("button", { name: "Send intro" });
    await userEvent.click(opener);

    const dialog = await screen.findByRole("dialog", { name: "Add 3 skills first" });
    // What the person already offers starts picked.
    const chips = within(dialog).getByRole("group", { name: "Skills you offer" });
    expect(within(chips).getByRole("button", { name: "React" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(dialog).getByRole("status")).toHaveTextContent("1 / 3");
    const save = within(dialog).getByRole("button", { name: "Save and continue" });
    expect(save).toBeDisabled();
    await userEvent.click(within(chips).getByRole("button", { name: "Figma" }));
    await userEvent.click(within(chips).getByRole("button", { name: "Python" }));
    expect(within(dialog).getByRole("status")).toHaveTextContent("3 / 3");
    await userEvent.click(save);

    expect(calls()[2]).toEqual({
      url: "/api/v1/me/onboarding/offers",
      method: "PUT",
      body: { skills: ["React", "Figma", "Python"] },
    });
    expect(calls()[3]).toMatchObject({ url: "/api/v1/matches/m1/intro" });
    expect(done).toHaveBeenCalledWith("sent");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it.each([
    [
      "Not now",
      (dialog: HTMLElement) =>
        userEvent.click(within(dialog).getByRole("button", { name: "Not now" })),
    ],
    // What a browser does on Escape (jsdom doesn't turn the key into this event itself).
    [
      "Escape",
      async (dialog: HTMLElement) => fireEvent(dialog, new Event("cancel", { cancelable: true })),
    ],
  ])("%s closes it and leaves the intro unsent", async (_, close) => {
    const done = vi.fn();
    fetchMock
      .mockResolvedValueOnce(json(409, SKILLS_REQUIRED))
      .mockResolvedValueOnce(json(200, progress({ offer_skills: [] })));
    render(<GatedSend onDone={done} />);
    await userEvent.click(screen.getByRole("button", { name: "Send intro" }));
    const dialog = await screen.findByRole("dialog", { name: "Add 3 skills first" });
    expect(within(dialog).getByRole("status")).toHaveTextContent("0 / 3");
    await close(dialog);
    await vi.waitFor(() => expect(done).toHaveBeenCalledWith(undefined));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("passes any other error on unchanged", async () => {
    fetchMock.mockResolvedValueOnce(
      json(409, { error: { ...SKILLS_REQUIRED.error, code: "intro_exists" } }),
    );
    const { result } = await (async () => {
      let caught: unknown = null;
      function Probe() {
        const { guard } = useSkillGate();
        return (
          <button
            type="button"
            onClick={() =>
              guard(async () => {
                const response = await fetch("/api/v1/matches/m1/intro", { method: "POST" });
                const { ApiError } = await import("@/lib/api/errors");
                throw new ApiError(response.status, await response.json(), undefined);
              }).catch((error: unknown) => {
                caught = error;
              })
            }
          >
            Go
          </button>
        );
      }
      render(<Probe />);
      await userEvent.click(screen.getByRole("button", { name: "Go" }));
      return { result: () => caught };
    })();
    await vi.waitFor(() => expect(result()).toMatchObject({ code: "intro_exists" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
