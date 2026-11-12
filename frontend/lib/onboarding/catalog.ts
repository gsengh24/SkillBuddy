/**
 * What the onboarding steps offer to tap (ADR 0022, mockups 01–04). Plain data and pure
 * helpers, so the steps only render. Picked chips are saved as plain strings (ADR 0020).
 */
import { INTENTS, intents, type Intent } from "@/lib/design/tokens";

export const TAG_MAX = 60;
export const MAX_TAGS = 20;
export const WANT_NOTE_MAX = 140;
export const NAME_MAX = 60;

export type IntentIconName =
  "build" | "exchange" | "buddy" | "accountability" | "mentor" | "explore";

/** Step 1's cards: the intent's label (from the design tokens), its icon and one line. */
export const INTENT_CARDS: { value: Intent; label: string; line: string; icon: IntentIconName }[] =
  INTENTS.map((value) => ({
    value,
    label: intents[value].label,
    ...{
      build_together: { line: "Find people to make a project with.", icon: "build" as const },
      skill_exchange: {
        line: "Teach what you know, learn what you don't.",
        icon: "exchange" as const,
      },
      interest_buddy: { line: "Someone to share a hobby with.", icon: "buddy" as const },
      accountability: {
        line: "A partner to keep each other on track.",
        icon: "accountability" as const,
      },
      mentor: { line: "Learn from, or guide, someone further along.", icon: "mentor" as const },
      explore: { line: "Just see who's out there.", icon: "explore" as const },
    }[value],
  }));

export type SkillGroup = { label: string; skills: string[] };

/** Step 2's chip clouds, and step 3's "Browse all skills". */
export const SKILL_GROUPS: SkillGroup[] = [
  {
    label: "Coding",
    skills: [
      "Python",
      "Java",
      "C++",
      "React",
      "Node.js",
      "Flutter",
      "Android",
      "Machine learning",
      "Data analysis",
      "SQL",
    ],
  },
  {
    label: "Design",
    skills: ["Figma", "UI design", "Graphic design", "Video editing", "3D modelling"],
  },
  { label: "Build", skills: ["Arduino", "Robotics", "CAD", "PCB design"] },
  {
    label: "Other",
    skills: ["Public speaking", "Writing", "Marketing", "Finance", "Photography", "Music"],
  },
];

export const INTERESTS = [
  "Chess",
  "Hackathons",
  "Startups",
  "Gaming",
  "Fitness",
  "Reading",
  "Music",
  "Open source",
  "Competitive programming",
  "Debate",
];

/**
 * Skills that people who offer a skill often look for. A small hand-made map: a nudge for
 * ordering only, never a rule. Keys and values are listed skills.
 */
const PAIRS_WITH: Record<string, string[]> = {
  Python: ["SQL", "Machine learning", "Data analysis", "React"],
  Java: ["Android", "SQL", "Node.js"],
  "C++": ["Python", "Arduino", "Machine learning"],
  React: ["Node.js", "SQL", "Figma", "UI design"],
  "Node.js": ["React", "SQL", "UI design"],
  Flutter: ["Node.js", "Figma", "UI design"],
  Android: ["Java", "UI design", "Node.js"],
  "Machine learning": ["Python", "Data analysis", "SQL"],
  "Data analysis": ["Python", "SQL", "Machine learning"],
  SQL: ["Python", "Data analysis", "Node.js"],
  Figma: ["React", "Flutter", "Android"],
  "UI design": ["React", "Flutter", "Node.js"],
  "Graphic design": ["Marketing", "Video editing", "Photography"],
  "Video editing": ["Graphic design", "Photography", "Music"],
  "3D modelling": ["CAD", "Robotics", "Arduino"],
  Arduino: ["PCB design", "Robotics", "Python"],
  Robotics: ["Arduino", "CAD", "Machine learning"],
  CAD: ["3D modelling", "Robotics", "PCB design"],
  "PCB design": ["Arduino", "CAD", "Robotics"],
  "Public speaking": ["Writing", "Marketing"],
  Writing: ["Public speaking", "Marketing", "UI design"],
  Marketing: ["Graphic design", "Writing", "Data analysis"],
  Finance: ["Data analysis", "Marketing", "Python"],
  Photography: ["Video editing", "Graphic design"],
  Music: ["Video editing", "Photography"],
};

const PAIRS_SHOWN = 6;

const same = (a: string, b: string) => a.toLocaleLowerCase() === b.toLocaleLowerCase();

export function includesTag(list: readonly string[], tag: string): boolean {
  return list.some((item) => same(item, tag));
}

/** Adds or removes a tag, ignoring case; a new tag goes at the end. */
export function toggleTag(list: readonly string[], tag: string): string[] {
  return includesTag(list, tag) ? list.filter((item) => !same(item, tag)) : [...list, tag];
}

/**
 * Step 3's "Pairs well with what you offer": skills often wanted by people who offer what
 * the person offers, most common first, never one they already offer. Ties keep map order.
 */
export function pairsWellWith(offers: readonly string[]): string[] {
  const score = new Map<string, number>();
  for (const offer of offers) {
    const key = Object.keys(PAIRS_WITH).find((skill) => same(skill, offer));
    for (const skill of (key ? PAIRS_WITH[key] : undefined) ?? []) {
      if (!includesTag(offers, skill)) score.set(skill, (score.get(skill) ?? 0) + 1);
    }
  }
  return [...score.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, PAIRS_SHOWN)
    .map(([skill]) => skill);
}

/** Tags picked that aren't on the listed chips (typed in through search), so they still show. */
export function extraTags(picked: readonly string[], listed: readonly string[]): string[] {
  return picked.filter((tag) => !includesTag(listed, tag));
}

export const ALL_LISTED_SKILLS = SKILL_GROUPS.flatMap((group) => group.skills);

export type StudyYear = "1" | "2" | "3" | "4" | "postgrad";
export const YEARS: { value: StudyYear; label: string }[] = [
  { value: "1", label: "1st" },
  { value: "2", label: "2nd" },
  { value: "3", label: "3rd" },
  { value: "4", label: "4th" },
  { value: "postgrad", label: "Postgrad" },
];

export type Branch =
  | "computer"
  | "electronics"
  | "electrical"
  | "mechanical"
  | "chemical"
  | "civil"
  | "biotechnology"
  | "other";
export const BRANCHES: { value: Branch; label: string }[] = [
  { value: "computer", label: "Computer Engineering" },
  { value: "electronics", label: "Electronics and Communication" },
  { value: "electrical", label: "Electrical" },
  { value: "mechanical", label: "Mechanical" },
  { value: "chemical", label: "Chemical" },
  { value: "civil", label: "Civil" },
  { value: "biotechnology", label: "Biotechnology" },
  { value: "other", label: "Other" },
];

export type Day = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";
export const DAYS: { value: Day; short: string; label: string }[] = [
  { value: "mon", short: "Mon", label: "Monday" },
  { value: "tue", short: "Tue", label: "Tuesday" },
  { value: "wed", short: "Wed", label: "Wednesday" },
  { value: "thu", short: "Thu", label: "Thursday" },
  { value: "fri", short: "Fri", label: "Friday" },
  { value: "sat", short: "Sat", label: "Saturday" },
  { value: "sun", short: "Sun", label: "Sunday" },
];

/** The stored bands (ADR 0022 keeps them; the mockup's 1–2, 3–5 … are not stored values). */
export type Hours = "1_3" | "4_6" | "7_10" | "10_plus";
export const HOURS: { value: Hours; label: string }[] = [
  { value: "1_3", label: "1–3" },
  { value: "4_6", label: "4–6" },
  { value: "7_10", label: "7–10" },
  { value: "10_plus", label: "10+" },
];
