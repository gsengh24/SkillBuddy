/**
 * The You page's data (design spec section 13): the editable draft, what changed, which
 * endpoint saves it, and the profile-strength checklist. No React here, so it is tested on
 * its own.
 */
import type { Profile } from "@/lib/api/schemas";
import { intents as INTENT_TOKENS, INTENTS, type Intent } from "@/lib/design/tokens";

import { MAX_LINKS } from "./limits";

/** Mirrors the API (backend/app/models/profile.py); the API is the real check. */
export const CITY_MAX = 80;
export const HEADLINE_MAX = 80;
export const GOAL_MAX = 300;

export type ExperienceLevel = NonNullable<Profile["experience_level"]>;
export type WorkingStyle = NonNullable<Profile["working_style"]>;
export type WeeklyHours = NonNullable<Profile["weekly_hours"]>;
export type Weekday = Profile["available_days"][number];
export type LocationPrecision = Profile["location_precision"];

export const EXPERIENCE: { value: ExperienceLevel; label: string }[] = [
  { value: "just_starting", label: "Just starting" },
  { value: "1_3_years", label: "1 to 3 years" },
  { value: "3_7_years", label: "3 to 7 years" },
  { value: "7_plus_years", label: "7+ years" },
];

export const WEEKLY_HOURS: { value: WeeklyHours; label: string }[] = [
  { value: "1_3", label: "1 to 3 hours" },
  { value: "4_6", label: "4 to 6 hours" },
  { value: "7_10", label: "7 to 10 hours" },
  { value: "10_plus", label: "10+ hours" },
];

export const WORKING_STYLES: { value: WorkingStyle; label: string }[] = [
  { value: "async", label: "Async" },
  { value: "mix", label: "Mix" },
  { value: "live", label: "Live sessions" },
];

export const DAYS: { value: Weekday; label: string; name: string }[] = [
  { value: "mon", label: "Mon", name: "Monday" },
  { value: "tue", label: "Tue", name: "Tuesday" },
  { value: "wed", label: "Wed", name: "Wednesday" },
  { value: "thu", label: "Thu", name: "Thursday" },
  { value: "fri", label: "Fri", name: "Friday" },
  { value: "sat", label: "Sat", name: "Saturday" },
  { value: "sun", label: "Sun", name: "Sunday" },
];

/**
 * "City" or "Hidden". "Country" is left out: the API stores only the city, so it would show
 * nothing, the same as "Hidden" (12A decision 4).
 */
export const LOCATION_CHOICES: { value: LocationPrecision; label: string }[] = [
  { value: "city", label: "City" },
  { value: "hidden", label: "Hidden" },
];

export const INTENT_CHOICES: { value: Intent; label: string }[] = INTENTS.map((value) => ({
  value,
  label: INTENT_TOKENS[value].label,
}));

/** Every half hour, as "HH:MM" with a 12-hour label ("6:30 PM"). */
export const TIMES: { value: string; label: string }[] = Array.from({ length: 48 }, (_, i) => {
  const hours = Math.floor(i / 2);
  const minutes = i % 2 ? "30" : "00";
  const label = `${hours % 12 || 12}:${minutes} ${hours < 12 ? "AM" : "PM"}`;
  return { value: `${String(hours).padStart(2, "0")}:${minutes}`, label };
});

/** Common zones; the saved one is added if it isn't here. */
export const TIMEZONES: { value: string; label: string }[] = [
  { value: "Asia/Kolkata", label: "India (Asia/Kolkata)" },
  { value: "Asia/Dubai", label: "Dubai (Asia/Dubai)" },
  { value: "Asia/Singapore", label: "Singapore (Asia/Singapore)" },
  { value: "Europe/London", label: "London (Europe/London)" },
  { value: "America/New_York", label: "New York (America/New_York)" },
  { value: "UTC", label: "UTC" },
];

export const OFFER_SUGGESTIONS = [
  "React",
  "Python",
  "UI design",
  "Writing",
  "Data analysis",
  "Marketing",
];
export const LEARN_SUGGESTIONS = ["TypeScript", "SQL", "Figma", "Public speaking", "Next.js", "ML"];

/** The ten sections, in the reference's order. */
export const SECTIONS = [
  { id: "s-basics", label: "Basics", title: "Basics" },
  { id: "s-skills", label: "Skills", title: "Skills" },
  { id: "s-looking", label: "Looking for", title: "Looking for" },
  { id: "s-avail", label: "Availability", title: "Availability" },
  { id: "s-links", label: "Links", title: "Links" },
  { id: "s-privacy", label: "Privacy", title: "Privacy and visibility" },
  { id: "s-alerts", label: "Alerts", title: "Alerts" },
  { id: "s-security", label: "Security", title: "Account and security" },
  { id: "s-data", label: "Your data", title: "Your data" },
  { id: "s-danger", label: "Danger zone", title: "Danger zone" },
] as const;
export type SectionId = (typeof SECTIONS)[number]["id"];

/** Link rows: the first link on each site goes in its row, anything else fills the gaps. */
export const LINK_ROWS = [
  { tile: "Web", label: "Portfolio", placeholder: "Portfolio or website", host: null },
  { tile: "Git", label: "GitHub", placeholder: "GitHub profile", host: "github.com" },
  { tile: "In", label: "LinkedIn", placeholder: "LinkedIn profile", host: "linkedin.com" },
] as const;

function hostOf(link: string): string {
  try {
    return new URL(link).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

export function linkSlots(links: string[]): string[] {
  const slots: string[] = Array(MAX_LINKS).fill("");
  const rest: string[] = [];
  for (const link of links) {
    const row = LINK_ROWS.findIndex((r) => r.host !== null && r.host === hostOf(link));
    if (row >= 0 && !slots[row]) slots[row] = link;
    else rest.push(link);
  }
  for (const link of rest) {
    const free = slots.indexOf("");
    if (free >= 0) slots[free] = link;
  }
  return slots;
}

export type Draft = {
  name: string;
  city: string;
  headline: string;
  about: string;
  languages: string[];
  experience: ExperienceLevel | "";
  offers: string[];
  seeks: string[];
  intents: Intent[];
  goal: string;
  style: WorkingStyle | null;
  hours: WeeklyHours | "";
  days: Weekday[];
  from: string;
  until: string;
  timezone: string;
  links: string[];
  location: LocationPrecision;
};

export function draftFrom(profile: Profile): Draft {
  return {
    name: profile.display_name,
    city: profile.city,
    headline: profile.headline,
    about: profile.about_text,
    languages: [...profile.languages],
    experience: profile.experience_level ?? "",
    offers: [...(profile.understanding?.offers ?? [])],
    seeks: [...(profile.understanding?.seeks ?? [])],
    intents: [...profile.intents],
    goal: profile.goal,
    style: profile.working_style,
    hours: profile.weekly_hours ?? "",
    days: [...profile.available_days],
    from: profile.available_from?.slice(0, 5) ?? "",
    until: profile.available_until?.slice(0, 5) ?? "",
    timezone: profile.timezone ?? "",
    links: linkSlots(profile.links),
    location: profile.location_precision,
  };
}

function same(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function isDirty(base: Draft, draft: Draft): boolean {
  return !same(base, draft);
}

const orNull = (value: string) => value || null;
const cleanLinks = (links: string[]) => links.map((l) => l.trim()).filter(Boolean);

/**
 * What a save sends. The about text can change only through PUT (it is re-read in the
 * background); skills are the parsed understanding (PUT /understanding); everything else is
 * one PATCH with only the changed fields.
 */
export function savePlan(base: Draft, draft: Draft) {
  const aboutChanged = draft.about.trim() !== base.about.trim();
  const skillsChanged = !same(base.offers, draft.offers) || !same(base.seeks, draft.seeks);
  const patch: Record<string, unknown> = {};
  const add = (key: keyof Draft, field: string, value: unknown) => {
    if (!same(base[key], draft[key])) patch[field] = value;
  };
  if (!aboutChanged) {
    // PUT sends these itself.
    add("name", "display_name", draft.name.trim());
    add("links", "links", cleanLinks(draft.links));
    add("languages", "languages", draft.languages);
    add("timezone", "timezone", orNull(draft.timezone));
  }
  add("city", "city", draft.city.trim());
  add("headline", "headline", draft.headline.trim());
  add("experience", "experience_level", orNull(draft.experience));
  add("intents", "intents", draft.intents);
  add("goal", "goal", draft.goal.trim());
  add("style", "working_style", draft.style);
  add("hours", "weekly_hours", orNull(draft.hours));
  add("days", "available_days", draft.days);
  add("from", "available_from", orNull(draft.from));
  add("until", "available_until", orNull(draft.until));
  add("location", "location_precision", draft.location);
  return { aboutChanged, skillsChanged, patch, links: cleanLinks(draft.links) };
}

export type Missing = { label: string; href: `#${SectionId}` };

/** The profile-strength checklist from the reference: share done, and what's left. */
export function strength(draft: Draft): { percent: number; missing: Missing[] } {
  const items: [string, boolean, `#${SectionId}`][] = [
    ["Add a headline", draft.headline.trim().length >= 10, "#s-basics"],
    ["Write a longer bio", draft.about.trim().length >= 120, "#s-basics"],
    ["Add 3 skills you offer", draft.offers.length >= 3, "#s-skills"],
    ["Add something to learn", draft.seeks.length >= 1, "#s-skills"],
    ["Pick an intent", draft.intents.length >= 1, "#s-looking"],
    ["Pick available days", draft.days.length >= 1, "#s-avail"],
    ["Add a link", draft.links.some((l) => l.trim()), "#s-links"],
    ["Share your goal", draft.goal.trim().length >= 20, "#s-looking"],
  ];
  const done = items.filter(([, ok]) => ok).length;
  return {
    percent: Math.round((done / items.length) * 100),
    missing: items.filter(([, ok]) => !ok).map(([label, , href]) => ({ label, href })),
  };
}
