import type { CSSProperties } from "react";

import { HUE_NAMES, hues, intents, type HueName, type Intent } from "./tokens";

/** WCAG 2.x relative luminance of a #RRGGBB colour. */
export function relativeLuminance(hex: string): number {
  const match = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!match?.[1]) throw new Error(`not a #RRGGBB colour: ${hex}`);
  const value = match[1];
  const [r, g, b] = [0, 2, 4].map((i) => {
    const channel = parseInt(value.slice(i, i + 2), 16) / 255;
    return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG contrast ratio, from 1 to 21. */
export function contrastRatio(foreground: string, background: string): number {
  const [light, dark] = [relativeLuminance(foreground), relativeLuminance(background)].sort(
    (a, b) => b - a,
  ) as [number, number];
  return (light + 0.05) / (dark + 0.05);
}

/**
 * A person's colour: a stable hash (FNV-1a) of their user id, picked from the six hues.
 * It depends on the id alone, never on anything about the person.
 */
export function personHue(userId: string): HueName {
  let hash = 0x811c9dc5;
  for (let i = 0; i < userId.length; i += 1) {
    hash ^= userId.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return HUE_NAMES[hash % HUE_NAMES.length] as HueName;
}

export function intentHue(intent: Intent): HueName {
  return intents[intent].hue;
}

/**
 * CSS variables for one hue, so a component can be written once and coloured per use:
 * `bg-(--hue-tint) text-(--hue-ink)`.
 */
export function hueStyle(hue: HueName): CSSProperties {
  const { base, ink, tint, edge, track } = hues[hue];
  return {
    "--hue-base": base,
    "--hue-ink": ink,
    "--hue-tint": tint,
    "--hue-edge": edge,
    "--hue-track": track,
  } as CSSProperties;
}
