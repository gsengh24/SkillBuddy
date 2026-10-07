/**
 * Design tokens: the Cynergi design system (ADR 0014, docs/design/design-spec.md).
 *
 * This file is the source of truth for colour values. app/globals.css repeats them as CSS
 * variables on :root and maps them into the Tailwind theme, and a test checks the two stay
 * identical.
 *
 * `colors` is the palette for new screens. The older names further down (`neutrals`, `hues`,
 * `greenSurfaces`, `badge`) belong to the components in `components/ui` that existing
 * screens still use; they point at the new palette where one exists and go away as each
 * screen is restyled.
 */

export const colors = {
  /** Page background. */
  bg: "#FFFFFF",
  /** Cards, composer, inactive segments. */
  panel: "#F6F7F5",
  /** Hairline borders and dividers (decorative: never the only edge of a control). */
  line: "#E4E6E2",
  /** Outer frames. */
  lineStrong: "#D9DBD6",
  /** Primary text and the primary button. */
  ink: "#0A0A0A",
  /** The primary button's hover fill (from the reference HTML). */
  inkHover: "#222222",
  /** Body text. */
  ink2: "#4A4F4A",
  /**
   * Muted text that must stay readable. The spec gives #6B6F6A, which is 4.44:1 on
   * green-tint; this is two steps darker so it passes 4.5:1 on every surface (ADR 0014).
   */
  muted: "#696D68",
  /** Second half of two-tone headlines (large bold text only), and field borders (3:1). */
  muted2: "#8A8F89",
  /** Decorative only, never text (2.1:1 on white). Numerals 01, 02, 03 use `muted`. */
  faint: "#B0B4AE",
  /** The brand: links, outline buttons, eyebrows, the CTA band. */
  green: "#0F4A34",
  greenHover: "#0B3828",
  /** Hero panel, soft badges. */
  greenTint: "#E8F1EC",
  /** Borders inside green-tint areas (decorative). */
  greenLine: "#B9D3C5",
  /** Chip fill on tint. */
  greenSoft: "#F3F9F5",
  /** Pixel-art fills and dots only. Never text. */
  mint: "#7BE0A8",
  /** Second line of a headline on the green CTA band. */
  mintText: "#9FD1B6",
  /** Errors, report and block confirmations. */
  danger: "#B3261E",
} as const;

export type ColorName = keyof typeof colors;

/** Radii in px: panels, cards, buttons, inputs, small chips. Pills use `rounded-full`. */
export const radii = { panel: 14, card: 12, control: 9, input: 10, chip: 4 } as const;

/** Content max width and side gutters in px. */
export const layout = { maxWidth: 1160, gutterPhone: 16, gutterDesktop: 32 } as const;

/**
 * An avatar's fill: green or ink, from a stable hash of the person's id (see
 * `avatarFill` in ./color.ts). Text on both is white.
 */
export const AVATAR_FILLS = ["green", "ink"] as const;
export type AvatarFill = (typeof AVATAR_FILLS)[number];

/* ------------------------------------------------------------------------------------- */
/* Older names, used by components/ui until each screen is restyled.                      */
/* ------------------------------------------------------------------------------------- */

export const neutrals = {
  ground: colors.bg,
  paper: colors.panel,
  ink: colors.ink,
  muted: colors.muted,
  line: colors.line,
  lineStrong: colors.lineStrong,
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
 * Green now uses the brand greens. The other hues keep their ADR 0010 values, except the
 * coral, blue, violet and teal tints, which are a little lighter so muted text still
 * reaches 4.5:1 on them.
 */
export const hues: Record<HueName, Hue> = {
  green: {
    base: colors.green,
    ink: colors.green,
    tint: colors.greenTint,
    edge: colors.greenLine,
    track: colors.greenLine,
  },
  amber: {
    base: "#D08A1E",
    ink: "#6E4608",
    tint: "#FDF3DC",
    edge: "#EBD2A8",
    track: "#F3DFB2",
  },
  coral: {
    base: "#E2573E",
    ink: "#9A3B27",
    tint: "#FCEAE4",
    edge: "#F0BFB2",
    track: "#F6D4CB",
  },
  blue: {
    base: "#3F78B5",
    ink: "#2A5683",
    tint: "#E4EFF9",
    edge: "#B5CCE0",
    track: "#CCDCE8",
  },
  violet: {
    base: "#7B63C2",
    ink: "#54428F",
    tint: "#F0EBF9",
    edge: "#D2C7EA",
    track: "#DFD6F1",
  },
  teal: {
    base: "#1F8A8C",
    ink: "#1B6466",
    tint: "#DFF2F1",
    edge: "#B5DCDA",
    track: "#C8E5E3",
  },
};

export const HUE_NAMES = Object.keys(hues) as HueName[];

/** Green-only surfaces, now the brand greens. */
export const greenSurfaces = {
  panel: colors.greenTint,
  chip: colors.greenSoft,
  chipEdge: colors.greenLine,
} as const;

/**
 * The filled notification badge. The coral base (#E2573E) gives only 3.6:1 under white
 * text, so the badge uses this darker coral (5.62:1).
 */
export const badge = { fill: "#B83D28", text: colors.bg } as const;

/** Focus ring colour: the brand green, on every focusable element. */
export const focusRing = colors.green;

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
