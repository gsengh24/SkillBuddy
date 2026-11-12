import { describe, expect, it } from "vitest";

import { homeRedirectFor, landingFor } from "./landing";

type State = "todo" | "saved" | "skipped";
const STEPS = ["intents", "offers", "wants", "about"] as const;

function progress(states: [State, State, State, State], completed = false) {
  return {
    completed_at: completed ? "2026-11-12T10:00:00Z" : null,
    steps: STEPS.map((step, i) => ({ step, state: states[i] as State })),
  };
}

describe("landing after sign-in", () => {
  it.each([
    ["a brand-new account", progress(["todo", "todo", "todo", "todo"]), "/onboarding"],
    ["part-way", progress(["saved", "skipped", "todo", "todo"]), "/onboarding"],
    [
      "every step saved or skipped",
      progress(["saved", "skipped", "skipped", "saved"]),
      "/onboarding/review",
    ],
    ["finished", progress(["saved", "saved", "saved", "saved"], true), "/home"],
    ["no answer from the API", null, "/home"],
  ])("%s → %s", (_, given, expected) => {
    expect(landingFor(given)).toBe(expected);
  });
});

describe("plain Home", () => {
  it("sends a person with a step still to do to the steps", () => {
    expect(homeRedirectFor(progress(["todo", "todo", "todo", "todo"]))).toBe("/onboarding");
    expect(homeRedirectFor(progress(["saved", "saved", "skipped", "todo"]))).toBe("/onboarding");
  });

  it("shows Home once every step is saved or skipped, when finished, or without an answer", () => {
    expect(homeRedirectFor(progress(["saved", "skipped", "skipped", "saved"]))).toBeNull();
    expect(homeRedirectFor(progress(["saved", "saved", "saved", "saved"], true))).toBeNull();
    expect(homeRedirectFor(null)).toBeNull();
  });
});
