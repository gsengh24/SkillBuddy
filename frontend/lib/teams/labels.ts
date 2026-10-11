import type { TeamPurpose } from "@/lib/api/schemas";

/** What a team is for, in words (the API sends the key). */
export const PURPOSE_LABELS: Record<TeamPurpose, string> = {
  hackathon: "Hackathon",
  project: "Project",
  study: "Study group",
  other: "Something else",
};

/** "3 of 6 people". */
export function teamSize(memberCount: number, maxMembers: number): string {
  return `${memberCount} of ${maxMembers} ${maxMembers === 1 ? "person" : "people"}`;
}

/** The short names on the Spaces page: the card tag and the purpose picker. */
export const SHORT_PURPOSE_LABELS: Record<TeamPurpose, string> = {
  hackathon: "Hackathon",
  project: "Project",
  study: "Study",
  other: "Other",
};

/** Shown when a space has no description yet. */
export const NO_DESCRIPTION = "No description yet.";
