import { describe, expect, it } from "vitest";

import type { Match } from "@/lib/api/schemas";

import { presentMatch, tidySentence, tidyTag, tidyTags } from "./present";

const CANDIDATE: Match["candidate"] = {
  user_id: "33333333-0000-4000-8000-000000000001",
  summary: "second-year ECE student interested in embedded systems",
  offers: ["electronics knowledge", "embedded systems expertise", "circuit design skills"],
  seeks: [],
  interests: ["electronics", "embedded systems", "analog VLSI", "circuit design"],
  availability: "Weekends",
  languages: ["en"],
};

describe("tidyTag", () => {
  it("drops a filler last word and starts with a capital", () => {
    expect(tidyTag("circuit design skills")).toBe("Circuit design");
    expect(tidyTag("  embedded   systems expertise ")).toBe("Embedded systems");
    expect(tidyTag("React")).toBe("React");
    expect(tidyTag("ui design")).toBe("UI design");
    expect(tidyTag("analog vlsi")).toBe("Analog VLSI");
  });

  it("leaves words with their own capitals, and a filler word on its own", () => {
    expect(tidyTag("iOS apps")).toBe("iOS apps");
    expect(tidyTag("analog VLSI")).toBe("Analog VLSI");
    expect(tidyTag("skills")).toBe("Skills");
    expect(tidyTag("  ")).toBe("");
  });
});

describe("tidyTags", () => {
  it("removes repeats and anything already shown", () => {
    expect(tidyTags(["React", "react skills", "", "Figma"])).toEqual(["React", "Figma"]);
    expect(tidyTags(["chess", "React"], ["React"])).toEqual(["Chess"]);
  });
});

describe("tidySentence", () => {
  it("capitalises and ends the sentence", () => {
    expect(tidySentence("builds  web apps")).toBe("Builds web apps.");
    expect(tidySentence("Builds web apps.")).toBe("Builds web apps.");
    expect(tidySentence("")).toBe("");
  });
});

describe("presentMatch", () => {
  it("uses the matcher's heading when there is one", () => {
    const view = presentMatch({ ...CANDIDATE, title: "Embedded systems builder" });
    expect(view.title).toBe("Embedded systems builder");
  });

  it("builds a heading from the tags for a profile read before headings existed", () => {
    const view = presentMatch(CANDIDATE);
    expect(view.title).toBe("Electronics · Embedded systems");
    expect(view.summary).toBe("Second-year ECE student interested in embedded systems.");
    expect(view.offers).toEqual(["Electronics", "Embedded systems", "Circuit design"]);
    // Only what the offers don't already say.
    expect(view.interests).toEqual(["Analog VLSI"]);
  });

  it("falls back to interests, then to a plain heading", () => {
    expect(presentMatch({ ...CANDIDATE, offers: [] }).title).toBe("Electronics · Embedded systems");
    expect(presentMatch({ ...CANDIDATE, offers: [], interests: [] }).title).toBe("Suggested match");
  });

  it("says where and when only if the person shares it", () => {
    expect(presentMatch({ ...CANDIDATE, location: "Patiala" }).meta).toBe(
      "Patiala · Available weekends",
    );
    expect(presentMatch({ ...CANDIDATE, location: null, availability: "" }).meta).toBe("");
  });
});
