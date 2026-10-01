import { describe, expect, it } from "vitest";

import { hueStyle, intentHue, personHue } from "./color";
import { HUE_NAMES, hues, INTENTS } from "./tokens";

describe("personHue", () => {
  it("is stable for the same id", () => {
    const id = "8d3f4b2a-0000-4000-8000-000000000001";
    expect(personHue(id)).toBe(personHue(id));
  });

  it("only returns palette hues and spreads ids across all six", () => {
    const seen = new Set<string>();
    for (let n = 0; n < 600; n += 1) {
      const hue = personHue(`00000000-0000-4000-8000-${n.toString().padStart(12, "0")}`);
      expect(HUE_NAMES).toContain(hue);
      seen.add(hue);
    }
    expect(seen.size).toBe(HUE_NAMES.length);
  });

  it("takes only an id: nothing about the person can influence it", () => {
    expect(personHue.length).toBe(1);
  });
});

describe("intents", () => {
  it("map to the agreed hues", () => {
    expect(INTENTS.map(intentHue)).toEqual(["green", "amber", "coral", "blue", "violet", "teal"]);
  });
});

describe("hueStyle", () => {
  it("exposes a hue as CSS variables", () => {
    expect(hueStyle("violet")).toEqual({
      "--hue-base": hues.violet.base,
      "--hue-ink": hues.violet.ink,
      "--hue-tint": hues.violet.tint,
      "--hue-edge": hues.violet.edge,
      "--hue-track": hues.violet.track,
    });
  });
});
