import { FeaturePaused } from "@/components/feature-paused";

/** Teams are switched off on the admin Settings page (A6); they start off (ADR 0016). */
export function TeamsPaused() {
  return (
    <FeaturePaused title="Teams aren't available right now">
      Teams are switched off for everyone at the moment. Anything already in a team is kept. Please
      check back later.
    </FeaturePaused>
  );
}
