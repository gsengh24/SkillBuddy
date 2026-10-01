import { badge, focusRing, greenSurfaces, HUE_NAMES, hues, neutrals } from "./tokens";

/**
 * Every foreground/background pairing the design system allows, with the WCAG level it
 * must meet. The contrast test checks each one; the style guide shows them.
 *
 * - "text": body text, 4.5:1.
 * - "large": text at 18.66px bold / 24px and up only, 3:1.
 * - "ui": borders, focus rings and state indicators of controls (WCAG 1.4.11), 3:1.
 */
export type PairKind = "text" | "large" | "ui";

export type ColourPair = {
  name: string;
  foreground: string;
  background: string;
  kind: PairKind;
};

export const MIN_RATIO: Record<PairKind, number> = { text: 4.5, large: 3, ui: 3 };

const neutralBackgrounds = {
  ground: neutrals.ground,
  paper: neutrals.paper,
  "green panel": greenSurfaces.panel,
  "green chip": greenSurfaces.chip,
} as const;

function textPairs(): ColourPair[] {
  const pairs: ColourPair[] = [];
  const backgrounds: Record<string, string> = { ...neutralBackgrounds };
  for (const hue of HUE_NAMES) backgrounds[`${hue} tint`] = hues[hue].tint;

  for (const [bgName, bg] of Object.entries(backgrounds)) {
    pairs.push({
      name: `ink on ${bgName}`,
      foreground: neutrals.ink,
      background: bg,
      kind: "text",
    });
    pairs.push({
      name: `muted on ${bgName}`,
      foreground: neutrals.muted,
      background: bg,
      kind: "text",
    });
  }
  for (const hue of HUE_NAMES) {
    const { ink, tint, track } = hues[hue];
    pairs.push({
      name: `${hue} ink on ${hue} tint`,
      foreground: ink,
      background: tint,
      kind: "text",
    });
    pairs.push({
      name: `${hue} ink on paper`,
      foreground: ink,
      background: neutrals.paper,
      kind: "text",
    });
    pairs.push({
      name: `${hue} ink on ground`,
      foreground: ink,
      background: neutrals.ground,
      kind: "text",
    });
    pairs.push({
      name: `${hue} ink on ${hue} track`,
      foreground: ink,
      background: track,
      kind: "text",
    });
  }
  pairs.push({
    name: "green ink on green panel",
    foreground: hues.green.ink,
    background: greenSurfaces.panel,
    kind: "text",
  });
  pairs.push({
    name: "badge text on badge fill",
    foreground: badge.text,
    background: badge.fill,
    kind: "text",
  });
  return pairs;
}

function uiPairs(): ColourPair[] {
  const pairs: ColourPair[] = [];
  for (const [bgName, bg] of Object.entries(neutralBackgrounds)) {
    pairs.push({
      name: `focus ring on ${bgName}`,
      foreground: focusRing,
      background: bg,
      kind: "ui",
    });
    pairs.push({
      name: `button outline (ink) on ${bgName}`,
      foreground: neutrals.ink,
      background: bg,
      kind: "ui",
    });
    pairs.push({
      name: `field underline (muted) on ${bgName}`,
      foreground: neutrals.muted,
      background: bg,
      kind: "ui",
    });
  }
  for (const hue of HUE_NAMES) {
    pairs.push({
      name: `selected chip border (${hue} ink) on paper`,
      foreground: hues[hue].ink,
      background: neutrals.paper,
      kind: "ui",
    });
  }
  pairs.push({
    name: "badge fill on paper",
    foreground: badge.fill,
    background: neutrals.paper,
    kind: "ui",
  });
  return pairs;
}

export const COLOUR_PAIRS: ColourPair[] = [...textPairs(), ...uiPairs()];
