/**
 * How a suggested person is worded on a match card. The matcher writes the heading and the
 * tags; this tidies what older profiles (read before it did) still hold, so every card
 * reads the same way. No React here, so it is tested on its own.
 */
import type { Match } from "@/lib/api/schemas";

type Candidate = Match["candidate"];

/** Tags shown per row; the rest are counted ("+2 more"). */
export const MAX_TAGS = 6;

// "circuit design skills" names circuit design; the last word adds nothing.
const FILLER = /\s+(knowledge|expertise|skills?|experience|basics)$/i;

// Written in lower case by older profiles; shown the usual way.
const ACRONYMS = new Set([
  "ai",
  "api",
  "aws",
  "cad",
  "css",
  "dsa",
  "html",
  "iot",
  "ml",
  "nlp",
  "pcb",
  "sql",
  "ui",
  "ux",
  "vlsi",
]);

/** One tag as the card shows it: no filler word, acronyms and the first letter in capitals. */
export function tidyTag(raw: string): string {
  const tag = raw
    .replace(/\s+/g, " ")
    .trim()
    .replace(FILLER, "")
    .split(" ")
    .map((word) => (ACRONYMS.has(word) ? word.toUpperCase() : word))
    .join(" ");
  const first = tag.split(" ")[0] ?? "";
  // A word with its own capitals (iOS, eBay) is left as written.
  return first && first === first.toLowerCase() ? tag.charAt(0).toUpperCase() + tag.slice(1) : tag;
}

/** Tidied tags, without repeats and without anything already in `shown`. */
export function tidyTags(items: string[], shown: string[] = []): string[] {
  const seen = new Set(shown.map((tag) => tag.toLowerCase()));
  const tags: string[] = [];
  for (const item of items) {
    const tag = tidyTag(item);
    const key = tag.toLowerCase();
    if (!tag || seen.has(key)) continue;
    seen.add(key);
    tags.push(tag);
  }
  return tags;
}

/** A sentence with a capital first letter and a full stop. */
export function tidySentence(raw: string): string {
  const text = raw.replace(/\s+/g, " ").trim();
  if (!text) return "";
  const sentence = text.charAt(0).toUpperCase() + text.slice(1);
  return /[.!?…]$/.test(sentence) ? sentence : `${sentence}.`;
}

export type MatchView = {
  /** The card heading: a few words, never the person's own sentence. */
  title: string;
  /** Where and when, e.g. "Patiala · Available weekends". */
  meta: string;
  summary: string;
  offers: string[];
  /** Interests that aren't already listed as something they offer. */
  interests: string[];
};

export function presentMatch(candidate: Candidate): MatchView {
  const offers = tidyTags(candidate.offers);
  const interests = tidyTags(candidate.interests, offers);
  const title =
    candidate.title?.trim() ||
    (offers.length ? offers : interests).slice(0, 2).join(" · ") ||
    "Suggested match";
  const availability = candidate.availability.replace(/\s+/g, " ").trim();
  const meta = [
    candidate.location?.trim(),
    availability ? `Available ${availability.charAt(0).toLowerCase()}${availability.slice(1)}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
  return { title, meta, summary: tidySentence(candidate.summary), offers, interests };
}
