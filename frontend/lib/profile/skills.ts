import { browserApi } from "@/lib/api/browser";
import { skillSuggestionsSchema } from "@/lib/api/schemas";

/** How many names the dropdown shows, and how long typing pauses before we ask. */
export const SKILL_SUGGESTION_LIMIT = 6;
export const SKILL_SUGGEST_DELAY_MS = 200;

/**
 * Skill names that match what has been typed (GET /skills/suggest). Only a convenience:
 * any tag can still be typed, so callers treat a failure as "no suggestions".
 */
export async function searchSkills(query: string): Promise<string[]> {
  const params = new URLSearchParams({ q: query, limit: String(SKILL_SUGGESTION_LIMIT) });
  const result = await browserApi(`/skills/suggest?${params}`, skillSuggestionsSchema, {
    timeoutMs: 5_000,
  });
  return result.items.map((item) => item.name);
}
