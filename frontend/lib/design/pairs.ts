import { badge, colors, focusRing, greenSurfaces, HUE_NAMES, hues, neutrals } from "./tokens";

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

/** The surfaces of the Cynergi palette that text and controls sit on. */
const surfaces = {
  bg: colors.bg,
  panel: colors.panel,
  "green tint": colors.greenTint,
  "green soft": colors.greenSoft,
} as const;

function pair(name: string, foreground: string, background: string, kind: PairKind) {
  return { name, foreground, background, kind };
}

/** Pairs of the Cynergi palette (ADR 0014). */
function cynergiPairs(): ColourPair[] {
  const pairs: ColourPair[] = [];
  for (const [surface, bg] of Object.entries(surfaces)) {
    pairs.push(pair(`ink on ${surface}`, colors.ink, bg, "text"));
    pairs.push(pair(`ink-2 on ${surface}`, colors.ink2, bg, "text"));
    pairs.push(pair(`muted on ${surface}`, colors.muted, bg, "text"));
    pairs.push(pair(`green on ${surface}`, colors.green, bg, "text"));
    pairs.push(pair(`danger on ${surface}`, colors.danger, bg, "text"));
    pairs.push(pair(`focus ring (green) on ${surface}`, focusRing, bg, "ui"));
    pairs.push(pair(`outline button border (green) on ${surface}`, colors.green, bg, "ui"));
  }
  // Two-tone headlines: the second half is large text only, never on green tint.
  for (const surface of ["bg", "panel", "green soft"] as const) {
    pairs.push(pair(`muted-2 on ${surface} (large)`, colors.muted2, surfaces[surface], "large"));
  }
  pairs.push(pair("green hover on bg", colors.greenHover, colors.bg, "text"));
  // Filled controls and chips: white text on ink, ink hover, green, green hover, danger.
  pairs.push(pair("white on ink (primary button, label chip)", colors.bg, colors.ink, "text"));
  pairs.push(pair("white on ink hover", colors.bg, colors.inkHover, "text"));
  pairs.push(pair("white on green (avatar, CTA band)", colors.bg, colors.green, "text"));
  pairs.push(pair("white on green hover", colors.bg, colors.greenHover, "text"));
  pairs.push(pair("white on danger", colors.bg, colors.danger, "text"));
  pairs.push(pair("ink on white button on green", colors.ink, colors.bg, "text"));
  pairs.push(pair("mint text on green (CTA second line)", colors.mintText, colors.green, "large"));
  // Field borders are the only edge of an input, so they need 3:1 against the white fill
  // and against the page. `line` is far too light for that.
  pairs.push(pair("field border (muted-2) on white fill", colors.muted2, colors.bg, "ui"));
  pairs.push(pair("field border (muted-2) on panel", colors.muted2, colors.panel, "ui"));
  pairs.push(pair("unread dot (green) on bg", colors.green, colors.bg, "ui"));
  pairs.push(pair("unread dot (green) on green tint", colors.green, colors.greenTint, "ui"));
  return pairs;
}

const legacyBackgrounds = {
  ground: neutrals.ground,
  paper: neutrals.paper,
  "green panel": greenSurfaces.panel,
  "green chip": greenSurfaces.chip,
} as const;

/** Pairs of the older components (components/ui), until each screen is restyled. */
function legacyTextPairs(): ColourPair[] {
  const pairs: ColourPair[] = [];
  const backgrounds: Record<string, string> = { ...legacyBackgrounds };
  for (const hue of HUE_NAMES) backgrounds[`${hue} tint`] = hues[hue].tint;

  for (const [bgName, bg] of Object.entries(backgrounds)) {
    pairs.push(pair(`legacy: ink on ${bgName}`, neutrals.ink, bg, "text"));
    pairs.push(pair(`legacy: muted on ${bgName}`, neutrals.muted, bg, "text"));
  }
  for (const hue of HUE_NAMES) {
    const { ink, tint, track } = hues[hue];
    pairs.push(pair(`${hue} ink on ${hue} tint`, ink, tint, "text"));
    pairs.push(pair(`${hue} ink on paper`, ink, neutrals.paper, "text"));
    pairs.push(pair(`${hue} ink on ground`, ink, neutrals.ground, "text"));
    pairs.push(pair(`${hue} ink on ${hue} track`, ink, track, "text"));
  }
  pairs.push(pair("green ink on green panel", hues.green.ink, greenSurfaces.panel, "text"));
  pairs.push(pair("badge text on badge fill", badge.text, badge.fill, "text"));
  return pairs;
}

function legacyUiPairs(): ColourPair[] {
  const pairs: ColourPair[] = [];
  for (const [bgName, bg] of Object.entries(legacyBackgrounds)) {
    pairs.push(pair(`legacy: focus ring on ${bgName}`, focusRing, bg, "ui"));
    pairs.push(pair(`legacy: button outline (ink) on ${bgName}`, neutrals.ink, bg, "ui"));
    pairs.push(pair(`legacy: field underline (muted) on ${bgName}`, neutrals.muted, bg, "ui"));
  }
  for (const hue of HUE_NAMES) {
    pairs.push(
      pair(`selected chip border (${hue} ink) on paper`, hues[hue].ink, neutrals.paper, "ui"),
    );
  }
  pairs.push(pair("badge fill on paper", badge.fill, neutrals.paper, "ui"));
  return pairs;
}

export const COLOUR_PAIRS: ColourPair[] = [
  ...cynergiPairs(),
  ...legacyTextPairs(),
  ...legacyUiPairs(),
];
