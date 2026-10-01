import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { contrastRatio, relativeLuminance } from "./color";
import { COLOUR_PAIRS, MIN_RATIO } from "./pairs";
import { badge, greenSurfaces, HUE_NAMES, hues, neutrals } from "./tokens";

describe("contrast", () => {
  it("matches known WCAG values", () => {
    expect(contrastRatio("#000000", "#FFFFFF")).toBeCloseTo(21, 5);
    expect(contrastRatio("#FFFFFF", "#FFFFFF")).toBeCloseTo(1, 5);
    expect(contrastRatio("#767676", "#FFFFFF")).toBeCloseTo(4.54, 2);
    expect(relativeLuminance("#FFFFFF")).toBeCloseTo(1, 5);
    expect(() => relativeLuminance("green")).toThrow(/RRGGBB/);
  });

  it.each(COLOUR_PAIRS.map((pair) => [pair.name, pair] as const))(
    "%s meets its minimum",
    (_name, pair) => {
      expect(contrastRatio(pair.foreground, pair.background)).toBeGreaterThanOrEqual(
        MIN_RATIO[pair.kind],
      );
    },
  );

  it("covers every hue's ink on its own tint, and the badge", () => {
    const names = new Set(COLOUR_PAIRS.map((pair) => pair.name));
    for (const hue of HUE_NAMES) expect(names).toContain(`${hue} ink on ${hue} tint`);
    expect(names).toContain("badge text on badge fill");
  });

  it("keeps base colours out of text: the coral base fails under badge text", () => {
    // Why the badge has its own darker fill.
    expect(contrastRatio(badge.text, hues.coral.base)).toBeLessThan(4.5);
    expect(contrastRatio(badge.text, badge.fill)).toBeGreaterThanOrEqual(4.5);
  });
});

describe("tokens and CSS stay in sync", () => {
  // Vitest runs from frontend/.
  const css = readFileSync(resolve(process.cwd(), "app/globals.css"), "utf8");
  const declared = new Map(
    [...css.matchAll(/--color-([a-z-]+):\s*(#[0-9a-f]{6})/gi)].map((match) => [
      match[1],
      match[2]?.toUpperCase(),
    ]),
  );

  const expected: Record<string, string> = {
    ground: neutrals.ground,
    paper: neutrals.paper,
    ink: neutrals.ink,
    muted: neutrals.muted,
    line: neutrals.line,
    "line-strong": neutrals.lineStrong,
    "green-panel": greenSurfaces.panel,
    "green-chip": greenSurfaces.chip,
    "green-chip-edge": greenSurfaces.chipEdge,
    badge: badge.fill,
    "badge-text": badge.text,
  };
  for (const hue of HUE_NAMES) {
    for (const [role, hex] of Object.entries(hues[hue])) expected[`${hue}-${role}`] = hex;
  }

  it.each(Object.entries(expected))("--color-%s is %s", (name, hex) => {
    expect(declared.get(name)).toBe(hex.toUpperCase());
  });

  it("declares no colour that is not a token", () => {
    expect([...declared.keys()].sort()).toEqual(Object.keys(expected).sort());
  });
});
