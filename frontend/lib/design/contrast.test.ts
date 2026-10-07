import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { contrastRatio, relativeLuminance } from "./color";
import { COLOUR_PAIRS, MIN_RATIO } from "./pairs";
import { badge, colors, greenSurfaces, HUE_NAMES, hues, neutrals } from "./tokens";

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

  it("covers every text colour of the palette on every surface", () => {
    const names = new Set(COLOUR_PAIRS.map((pair) => pair.name));
    for (const surface of ["bg", "panel", "green tint", "green soft"]) {
      for (const text of ["ink", "ink-2", "muted", "green", "danger"]) {
        expect(names).toContain(`${text} on ${surface}`);
      }
      expect(names).toContain(`focus ring (green) on ${surface}`);
    }
  });

  it("keeps base colours out of text: the coral base fails under badge text", () => {
    // Why the badge has its own darker fill.
    expect(contrastRatio(badge.text, hues.coral.base)).toBeLessThan(4.5);
    expect(contrastRatio(badge.text, badge.fill)).toBeGreaterThanOrEqual(4.5);
  });

  it("keeps the restricted colours where they are allowed", () => {
    // muted-2 is large text only; faint and mint are never text; line is never the only
    // edge of a control. Each of these would fail if used for body text or a field border.
    expect(contrastRatio(colors.muted2, colors.bg)).toBeLessThan(MIN_RATIO.text);
    expect(contrastRatio(colors.muted2, colors.greenTint)).toBeLessThan(MIN_RATIO.large);
    expect(contrastRatio(colors.faint, colors.bg)).toBeLessThan(MIN_RATIO.large);
    expect(contrastRatio(colors.mint, colors.bg)).toBeLessThan(MIN_RATIO.large);
    expect(contrastRatio(colors.line, colors.bg)).toBeLessThan(MIN_RATIO.ui);
    // Why muted is darker than the spec's #6B6F6A: that value fails on green tint.
    expect(contrastRatio("#6B6F6A", colors.greenTint)).toBeLessThan(MIN_RATIO.text);
  });
});

describe("tokens and CSS stay in sync", () => {
  // Vitest runs from frontend/.
  const css = readFileSync(resolve(process.cwd(), "app/globals.css"), "utf8");
  const rootBlock = /:root\s*\{([^}]*)\}/.exec(css)?.[1] ?? "";
  const rootVars = new Map(
    [...rootBlock.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-f]{6})/gi)].map((match) => [
      match[1],
      match[2]?.toUpperCase(),
    ]),
  );
  // Theme colours are either a hex value or var(--<root variable>).
  const themeColours = new Map(
    [...css.matchAll(/--color-([a-z0-9-]+):\s*(#[0-9a-f]{6}|var\(--([a-z0-9-]+)\))/gi)].map(
      (match) => [match[1], (match[3] ? rootVars.get(match[3]) : match[2])?.toUpperCase()],
    ),
  );

  const kebab = (name: string) => name.replace(/([A-Z0-9])/g, (c) => `-${c.toLowerCase()}`);
  const palette: Record<string, string> = {};
  for (const [name, hex] of Object.entries(colors)) palette[kebab(name)] = hex;

  it.each(Object.entries(palette))("--%s on :root is %s", (name, hex) => {
    expect(rootVars.get(name)).toBe(hex.toUpperCase());
  });

  it("declares nothing on :root that is not a palette colour", () => {
    expect([...rootVars.keys()].sort()).toEqual(Object.keys(palette).sort());
  });

  const expected: Record<string, string> = {
    ...palette,
    ground: neutrals.ground,
    paper: neutrals.paper,
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
    expect(themeColours.get(name)).toBe(hex.toUpperCase());
  });

  it("declares no colour that is not a token", () => {
    expect([...themeColours.keys()].sort()).toEqual(Object.keys(expected).sort());
  });
});
