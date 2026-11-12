import { describe, expect, it } from "vitest";

import { extraTags, INTENT_CARDS, pairsWellWith, SKILL_GROUPS, toggleTag } from "./catalog";
import { stepAfter, stepNumber, stepToShow } from "./steps";

const progress = (saved: string[], next: "intents" | "offers" | "wants" | "about" | "review") => ({
  next_step: next,
  steps: (["intents", "offers", "wants", "about"] as const).map((step) => ({
    step,
    state: saved.includes(step) ? "saved" : "todo",
  })),
});

describe("onboarding steps", () => {
  it("numbers the steps and goes to review after the last", () => {
    expect(stepNumber("intents")).toBe(1);
    expect(stepNumber("about")).toBe(4);
    expect(stepAfter("wants")).toBe("about");
    expect(stepAfter("about")).toBe("review");
  });

  it("resumes where the person left off", () => {
    expect(stepToShow(null, progress(["intents"], "offers"))).toBe("offers");
    expect(stepToShow("nonsense", progress(["intents"], "wants"))).toBe("wants");
  });

  it("opens a step the person asks for, but nothing past step 1 before it is saved", () => {
    expect(stepToShow("offers", progress(["intents", "offers"], "wants"))).toBe("offers");
    expect(stepToShow("about", progress([], "intents"))).toBe("intents");
    expect(stepToShow("intents", progress([], "intents"))).toBe("intents");
  });
});

describe("onboarding catalog", () => {
  it("has one card per intent, labelled as everywhere else", () => {
    expect(INTENT_CARDS.map((card) => card.label)).toEqual([
      "Build together",
      "Skill exchange",
      "Interest buddy",
      "Accountability",
      "Mentor",
      "Explore",
    ]);
  });

  it("toggles tags ignoring case", () => {
    expect(toggleTag(["React"], "react")).toEqual([]);
    expect(toggleTag(["React"], "SQL")).toEqual(["React", "SQL"]);
  });

  it("orders pairings by how many offers point at them and never repeats an offer", () => {
    const pairs = pairsWellWith(["React", "Figma"]);
    expect(pairs[0]).toBe("Node.js");
    expect(pairs).not.toContain("React");
    expect(pairs).not.toContain("Figma");
    expect(pairs.length).toBeLessThanOrEqual(6);
    expect(pairsWellWith([])).toEqual([]);
    expect(pairsWellWith(["Underwater basket weaving"])).toEqual([]);
  });

  it("every pairing is a listed skill", () => {
    const listed = SKILL_GROUPS.flatMap((g) => g.skills);
    for (const skill of listed) {
      for (const pair of pairsWellWith([skill])) expect(listed).toContain(pair);
    }
  });

  it("finds typed-in tags that aren't on the chips", () => {
    expect(extraTags(["React", "Django"], ["react", "SQL"])).toEqual(["Django"]);
  });
});
