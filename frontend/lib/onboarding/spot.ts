/**
 * Finds known skill and interest names in already-redacted text, on the device (ADR 0023).
 * Only names from the bundled lists are suggested (ADR 0020), so a stray word never turns
 * into a chip; the person then confirms each one.
 */
import { INTERESTS, MAX_TAGS, SKILL_GROUPS, includesTag } from "./catalog";

/** Short forms people write, mapped to the listed name. Keys are lower case. */
const ALIASES: Record<string, string> = {
  ml: "Machine learning",
  "deep learning": "Machine learning",
  ai: "Machine learning",
  js: "JavaScript",
  ts: "TypeScript",
  "react.js": "React",
  reactjs: "React",
  "react native": "React",
  node: "Node.js",
  nodejs: "Node.js",
  "ui/ux": "UI design",
  ux: "UX design",
  "public-speaking": "Public speaking",
  debating: "Debate",
  "street photography": "Photography",
  hackathon: "Hackathons",
  startup: "Startups",
  "competitive coding": "Competitive programming",
  gym: "Fitness",
};

/** Hobbies and pastimes: suggested as interests, not as skills you offer. */
const HOBBIES = [
  ...INTERESTS,
  "Football",
  "Cricket",
  "Badminton",
  "Basketball",
  "Running",
  "Yoga",
  "Gym training",
  "Hiking",
  "Cycling",
  "Swimming",
  "Cooking",
  "Baking",
  "Gardening",
  "Travel",
  "Dancing",
  "Meditation",
  "Journaling",
  "Photography",
];

/** Listed names too general to suggest from a resume ("Languages: English, Hindi"). */
const TOO_GENERAL = ["Languages"];

export type Found = { skills: string[]; interests: string[] };

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Where `name` first appears as a whole word or phrase, or -1. */
function firstIndex(text: string, name: string): number {
  // Letters, digits, + and # count as part of a word ("C++", "C#"), so "C" never matches them.
  const pattern = new RegExp(`(?<![\\p{L}\\p{N}+#])${escape(name)}(?![\\p{L}\\p{N}+#])`, "iu");
  return text.search(pattern);
}

/**
 * The listed names found in `text`, in the order they first appear, split into skills and
 * interests, at most MAX_TAGS of each. `names` is the bundled list (GET /skills/common); the
 * onboarding chips are always included.
 */
export function spotSkills(text: string, names: readonly string[]): Found {
  const known: string[] = [];
  for (const name of [...SKILL_GROUPS.flatMap((group) => group.skills), ...HOBBIES, ...names]) {
    if (name.trim() && !includesTag(known, name) && !includesTag(TOO_GENERAL, name)) {
      known.push(name);
    }
  }

  const hits: { name: string; at: number }[] = [];
  const add = (name: string, at: number) => {
    const existing = hits.find((hit) => hit.name.toLowerCase() === name.toLowerCase());
    if (!existing) hits.push({ name, at });
    else existing.at = Math.min(existing.at, at);
  };
  for (const name of known) {
    const at = firstIndex(text, name);
    if (at >= 0) add(name, at);
  }
  for (const [alias, name] of Object.entries(ALIASES)) {
    const at = firstIndex(text, alias);
    if (at >= 0) add(known.find((item) => item.toLowerCase() === name.toLowerCase()) ?? name, at);
  }

  hits.sort((a, b) => a.at - b.at);
  const skills: string[] = [];
  const interests: string[] = [];
  for (const { name } of hits) {
    const list = includesTag(HOBBIES, name) ? interests : skills;
    if (list.length < MAX_TAGS) list.push(name);
  }
  return { skills, interests };
}
