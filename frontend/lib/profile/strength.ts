/**
 * Words and links for the API's profile-strength items (ADR 0022). The API decides what is
 * done; this only says how to show what isn't. Unknown codes from a newer API are skipped.
 */
import type { Strength } from "@/lib/api/schemas";

import type { SectionId } from "./you";

export type Missing = { label: string; href: `#${SectionId}` };

const ITEMS: Record<string, Missing> = {
  intents: { label: "Pick what you're here for", href: "#s-looking" },
  offers: { label: "Add 3 skills you offer", href: "#s-skills" },
  wants: { label: "Add what you're looking for", href: "#s-skills" },
  about_text: { label: "Write a short bio", href: "#s-basics" },
  availability: { label: "Add availability", href: "#s-avail" },
  headline: { label: "Add a headline", href: "#s-basics" },
  links: { label: "Add a link", href: "#s-links" },
};

export function missingItems(strength: Strength | null): Missing[] {
  return (strength?.missing ?? []).flatMap((code) => {
    const item = ITEMS[code];
    return item ? [item] : [];
  });
}

/** What the "Finish your profile" popup needs, or null when there is nothing to show. */
export function nudgeStrength(
  strength: Strength | null,
): { done: number; total: number; missing: Missing[] } | null {
  if (!strength) return null;
  return { done: strength.done, total: strength.total, missing: missingItems(strength) };
}
