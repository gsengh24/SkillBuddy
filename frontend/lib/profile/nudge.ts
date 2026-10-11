/**
 * Whether Home shows the "Finish your profile" popup. One pure rule, so the component only
 * renders and animates.
 */
import type { Missing } from "./you";

/** localStorage key holding the `session_started_at` the popup was last closed in. */
export const NUDGE_DISMISSED_KEY = "cynergi:profile-nudge-dismissed";

/** A sign-in this long after the account was made is a returning one, not the first. */
const RETURNING_AFTER_MS = 5 * 60 * 1000;

export type NudgeStrength = { done: number; total: number; missing: Missing[] };

export function shouldShowProfileNudge({
  user,
  strength,
  dismissedFor,
}: {
  user: { created_at: string; session_started_at?: string | null };
  /** Null when the person has no profile yet: onboarding handles that. */
  strength: NudgeStrength | null;
  /** The `session_started_at` the popup was closed in, if it ever was. */
  dismissedFor: string | null;
}): boolean {
  if (!strength || strength.missing.length === 0) return false;
  const started = user.session_started_at;
  if (!started) return false;
  const gap = Date.parse(started) - Date.parse(user.created_at);
  if (!(gap > RETURNING_AFTER_MS)) return false;
  return dismissedFor !== started;
}
