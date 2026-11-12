import type { Onboarding } from "@/lib/api/schemas";

/**
 * Where a signed-in person lands (ADR 0022, "Landing after sign-in"). Pure, for tests; the
 * rule reads only the onboarding progress the API returns (GET /me/onboarding).
 */
export const HOME_PATH = "/home";
export const ONBOARDING_PATH = "/onboarding";
export const REVIEW_PATH = "/onboarding/review";

type Progress = Pick<Onboarding, "completed_at" | "steps">;

function stepsLeft(progress: Progress): boolean {
  return progress.steps.some((step) => step.state === "todo");
}

/**
 * After sign-in, with no deep link: a step still to do opens the steps (they resume where
 * the person left off), all steps saved or skipped opens step 5, and a finished profile (or
 * no answer from the API) goes Home.
 */
export function landingFor(progress: Progress | null): string {
  if (!progress || progress.completed_at) return HOME_PATH;
  return stepsLeft(progress) ? ONBOARDING_PATH : REVIEW_PATH;
}

/**
 * Plain Home (no opened item, no filter) while a step is still to do sends the person to the
 * steps, so a refresh or bookmark doesn't land on an empty Home. Null: show Home. Once every
 * step is saved or skipped, Home shows "Finish your profile" instead.
 */
export function homeRedirectFor(progress: Progress | null): string | null {
  if (!progress || progress.completed_at) return null;
  return stepsLeft(progress) ? ONBOARDING_PATH : null;
}
