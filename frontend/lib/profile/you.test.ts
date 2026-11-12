import { describe, expect, it } from "vitest";

import { profileSchema } from "@/lib/api/schemas";

import { missingItems, nudgeStrength } from "./strength";
import { TIMES, draftFrom, isDirty, linkSlots, savePlan } from "./you";

const PROFILE = profileSchema.parse({
  user_id: "u1",
  display_name: "Asha",
  about_text: "I build React apps and write Python, weekends.",
  links: [],
  timezone: null,
  languages: [],
  visibility: "matchable",
  parse_status: "pending",
  parse_source: null,
  understanding: null,
  ai_consent_version: "v1",
  ai_consent_at: null,
  ai_consent_current: true,
  created_at: "2026-10-08T00:00:00Z",
  updated_at: "2026-10-08T00:00:00Z",
});

describe("linkSlots", () => {
  it("puts GitHub and LinkedIn links in their rows and the rest in the gaps", () => {
    expect(
      linkSlots(["https://www.linkedin.com/in/a", "https://a.dev", "https://github.com/a"]),
    ).toEqual(["https://a.dev", "https://github.com/a", "https://www.linkedin.com/in/a"]);
    // Two portfolio links: the second takes a free row rather than being dropped.
    expect(linkSlots(["https://a.dev", "https://b.dev"])).toEqual([
      "https://a.dev",
      "https://b.dev",
      "",
    ]);
    expect(linkSlots([])).toEqual(["", "", ""]);
  });
});

describe("savePlan", () => {
  it("sends only what changed, with empty values as null", () => {
    const base = draftFrom(PROFILE);
    const plan = savePlan(base, {
      ...base,
      city: " Pune ",
      experience: "",
      hours: "4_6",
      from: "18:00",
      days: ["sat", "sun"],
    });
    expect(plan.aboutChanged).toBe(false);
    expect(plan.patch).toEqual({
      city: "Pune",
      weekly_hours: "4_6",
      available_from: "18:00",
      available_days: ["sat", "sun"],
    });
  });

  it("leaves name, links, languages and time zone to PUT when the description changed", () => {
    const base = draftFrom(PROFILE);
    const plan = savePlan(base, {
      ...base,
      about: `${base.about} More.`,
      name: "Asha K",
      timezone: "Asia/Kolkata",
      goal: "Ship it",
    });
    expect(plan.aboutChanged).toBe(true);
    expect(plan.patch).toEqual({ goal: "Ship it" });
  });

  it("saves skill changes to the chip columns (ADR 0022) and nothing else", () => {
    const base = draftFrom({ ...PROFILE, offer_skills: ["Go"], want_skills: ["Figma"] });
    expect(base.offers).toEqual(["Go"]);
    expect(base.seeks).toEqual(["Figma"]);
    const draft = { ...base, offers: ["Go", "React"] };
    expect(isDirty(base, draft)).toBe(true);
    expect(savePlan(base, draft).patch).toEqual({ offer_skills: ["Go", "React"] });
    expect(isDirty(base, { ...base })).toBe(false);
  });
});

describe("strength words", () => {
  it("names the API's missing items, links each to its section, and skips unknown ones", () => {
    const strength = {
      percent: 29,
      done: 2,
      total: 7,
      missing: ["availability", "links", "something_new", "wants"],
    };
    expect(missingItems(strength)).toEqual([
      { label: "Add availability", href: "#s-avail" },
      { label: "Add a link", href: "#s-links" },
      { label: "Add what you're looking for", href: "#s-skills" },
    ]);
    expect(missingItems(null)).toEqual([]);
    expect(nudgeStrength(strength)).toMatchObject({ done: 2, total: 7 });
    expect(nudgeStrength(null)).toBeNull();
  });
});

describe("TIMES", () => {
  it("lists every half hour with a 12-hour label", () => {
    expect(TIMES).toHaveLength(48);
    expect(TIMES[0]).toEqual({ value: "00:00", label: "12:00 AM" });
    expect(TIMES[37]).toEqual({ value: "18:30", label: "6:30 PM" });
  });
});
