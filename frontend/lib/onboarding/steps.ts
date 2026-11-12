/** The order of the onboarding steps and which one to show (ADR 0022). Pure, for tests. */
export const STEPS = ["intents", "offers", "wants", "about"] as const;
export type Step = (typeof STEPS)[number];
export type NextStep = Step | "review";

export function isStep(value: unknown): value is Step {
  return typeof value === "string" && (STEPS as readonly string[]).includes(value);
}

/** 1-based number shown as "Step n of 4". */
export function stepNumber(step: Step): number {
  return STEPS.indexOf(step) + 1;
}

export function stepAfter(step: Step): NextStep {
  const next = STEPS[STEPS.indexOf(step) + 1];
  return next ?? "review";
}

export function stepBefore(step: Step): Step | null {
  return STEPS[STEPS.indexOf(step) - 1] ?? null;
}

/**
 * The step to open: one the person asked for (?step=, e.g. "Back" or "Edit") if they have
 * reached it, otherwise where they left off. Step 1 must be saved before any other.
 */
export function stepToShow(
  requested: unknown,
  progress: { next_step: NextStep | null; steps: { step: Step; state: string }[] },
): Step | "review" {
  const intentsSaved = progress.steps.some((s) => s.step === "intents" && s.state === "saved");
  if (isStep(requested) && (requested === "intents" || intentsSaved)) return requested;
  return progress.next_step ?? "review";
}
