/**
 * Design tokens for direction B, "Quiet dashboard" (ADR 0010, docs/design/design-system.md).
 *
 * This file is the source of truth for colour values. app/globals.css repeats them as CSS
 * variables in the Tailwind theme, and a test checks the two stay identical.
 *
 * Rules: a hue's `base` is for dots, bars and fills only, never text. Text on a tint uses
 * that hue's `ink`. Colour never encodes a personal attribute.
 */

export const neutrals = {
  ground: "#F2F6F0",
  paper: "#FBFDF9",
  ink: "#14201A",
  muted: "#55655B",
  line: "#D3DCD1",
  lineStrong: "#B9C7B8",
} as const;

export type HueName = "green" | "amber" | "coral" | "blue" | "violet" | "teal";

export type Hue = {
  /** Dots, bars and fills only. Never text. */
  base: string;
  /** Text on this hue's tint (and on paper or ground). */
  ink: string;
  /** Backgrounds. */
  tint: string;
  /** Borders of tinted elements (tags). */
  edge: string;
  /** The unfilled part of a bar. */
  track: string;
};

/**
 * Values marked "derived" were not in the brief; they mix the hue's base into paper at the
 * same strength as the given ones (edge about 37%, track about 25%). See the design doc.
 */
export const hues: Record<HueName, Hue> = {
  green: {
    base: "#2C6A4C",
    ink: "#1F5238",
    tint: "#E1F0E4",
    edge: "#C5D8C8", // the brief's chip-edge
    track: "#C7D8CE", // derived
  },
  amber: {
    base: "#D08A1E",
    ink: "#6E4608",
    tint: "#FDF3DC",
    edge: "#EBD2A8", // derived
    track: "#F3DFB2",
  },
  coral: {
    base: "#E2573E",
    ink: "#9A3B27",
    tint: "#FBE4DD",
    edge: "#F0BFB2",
    track: "#F6D4CB",
  },
  blue: {
    base: "#3F78B5",
    ink: "#2A5683",
    tint: "#E0ECF8",
    edge: "#B5CCE0", // derived
    track: "#CCDCE8", // derived
  },
  violet: {
    base: "#7B63C2",
    ink: "#54428F",
    tint: "#ECE6F7",
    edge: "#D2C7EA",
    track: "#DFD6F1",
  },
  teal: {
    base: "#1F8A8C",
    ink: "#1B6466",
    tint: "#DDF0EF",
    edge: "#B5DCDA",
    track: "#C8E5E3",
  },
};

export const HUE_NAMES = Object.keys(hues) as HueName[];

/** Green-only surfaces from the brief. */
export const greenSurfaces = {
  panel: "#DDEFE1",
  chip: "#EDF6EE",
  chipEdge: "#C5D8C8",
} as const;

/**
 * The filled notification badge. The coral base (#E2573E) gives only 3.71:1 under paper
 * text, so the badge uses this darker coral (5.49:1).
 */
export const badge = { fill: "#B83D28", text: neutrals.paper } as const;

/** Focus ring: 2px, offset 2px, on every focusable element. */
export const focusRing = hues.green.base;

export type Intent =
  "build_together" | "skill_exchange" | "interest_buddy" | "accountability" | "mentor" | "explore";

export const intents: Record<Intent, { label: string; hue: HueName }> = {
  build_together: { label: "Build together", hue: "green" },
  skill_exchange: { label: "Skill exchange", hue: "amber" },
  interest_buddy: { label: "Interest buddy", hue: "coral" },
  accountability: { label: "Accountability", hue: "blue" },
  mentor: { label: "Mentor", hue: "violet" },
  explore: { label: "Explore", hue: "teal" },
};

export const INTENTS = Object.keys(intents) as Intent[];

export const radii = { card: 18, hero: 22, why: 12 } as const;
