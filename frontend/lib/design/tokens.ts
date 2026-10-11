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
  bg: "#0B0C0B",
  /** Cards, composer, inactive segments. */
  panel: "#141614",
  /** Hairline borders and dividers (decorative: never the only edge of a control). */
  line: "#262826",
  /** Outer frames. */
  lineStrong: "#323532",
  /** Primary text and the primary button. */
  ink: "#F3F4F1",
  /** The primary button's hover fill (from the reference HTML). */
  inkHover: "#FFFFFF",
  /** Body text. */
  ink2: "#C9CCC6",
  /**
   * Muted text that must stay readable. The spec gives #6B6F6A, which is 4.44:1 on
   * green-tint; this is two steps darker so it passes 4.5:1 on every surface (ADR 0014).
   */
  muted: "#A9ADA7",
  /** Second half of two-tone headlines (large bold text only), and field borders (3:1). */
  muted2: "#8A8E88",
  /** Decorative only, never text (2.1:1 on white). Numerals 01, 02, 03 use `muted`. */
  faint: "#4A4D49",
  /** The brand: links, outline buttons, eyebrows, the CTA band. */
  green: "#7BE0A8",
  greenHover: "#9FD1B6",
  /** Hero panel, soft badges. */
  greenTint: "#142219",
  /** Borders inside green-tint areas (decorative). */
  greenLine: "#2A4536",
  /** Chip fill on tint. */
  greenSoft: "#101A14",
  /** Pixel-art fills and dots only. Never text. */
  mint: "#7BE0A8",
  /** Second line of a headline on the green CTA band. */
  mintText: "#9FD1B6",
  /**
   * Second half of a two-tone headline on a green band. Light: mint on the dark green. Dark
   * theme overrides it (see `darkBand`) because the band turns mint there.
   */
  onGreen2: "#256040",
  /** Errors, report and block confirmations. */
  danger: "#FF8A80",
  /** The surface of cards and text boxes: white in light, a step above the page in dark. */
  card: "#111311",
  /** The inbox pane on Home: ink in every theme, like the landing page's dark sections. */
  pane: "#0F100F",
  pane2: "#1A1C1A",
  paneLine: "#262826",
  /** Text on the pane: primary, secondary, tertiary (all 4.5:1 or better on `pane`). */
  onDark: "#F3F4F1",
  onDark2: "#A9ADA7",
  onDark3: "#8A8E88",
  /** Avatar fills on the pane (green and ink), the same in every theme. */
  paneGreen: "#0F4A34",
  paneInk: "#2B2D2B",
  /** "Needs a reply" on the pane. Text on `pane` only. */
  amber: "#E8A06F",
} as const;

/**
 * The green band in the dark theme: `--green` is mint, the headline is the page background
 * and its second half is `--on-green-2`. globals.css repeats these; the contrast test covers them.
 */
export const darkBand = {
  surface: "#7BE0A8",
  headline: "#0B0C0B",
  headlineMuted: "#256040",
} as const;

export type ColorName = keyof typeof colors;

/**
 * Letter-spacing for display headlines (design spec section 3): -0.03em up to 52px and
 * -0.04em from 56px up, never tighter (at -0.05em the letters touched). Mirrored in
 * app/globals.css as --tracking-display and --tracking-display-xl.
 */
export const displayTracking = { upTo52px: "-0.03em", from56px: "-0.04em" } as const;

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
    ink: "#F0C377",
    tint: "#2B2110",
    edge: "#5A4420",
    track: "#3F2F14",
  },
  coral: {
    base: "#E2573E",
    ink: "#F4A08F",
    tint: "#2D1814",
    edge: "#5E2F26",
    track: "#432019",
  },
  blue: {
    base: "#3F78B5",
    ink: "#9CC3EA",
    tint: "#121F2C",
    edge: "#2B4A68",
    track: "#1F3448",
  },
  violet: {
    base: "#7B63C2",
    ink: "#C5B6EE",
    tint: "#1D1830",
    edge: "#44386E",
    track: "#2D2549",
  },
  teal: {
    base: "#1F8A8C",
    ink: "#7FD0D2",
    tint: "#0F2625",
    edge: "#24605F",
    track: "#183B3A",
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
export const badge = { fill: "#FF8E7A", text: colors.bg } as const;

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
