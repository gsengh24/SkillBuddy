import { FeaturePaused } from "@/components/feature-paused";

/** Pair spaces (teams) are switched off on the admin Settings page (A6); they start off (ADR 0016, 0018). */
export function TeamsPaused() {
  return (
    <FeaturePaused title="Pair spaces aren't available right now">
      Pair spaces are switched off for everyone at the moment. Anything already in a pair space is
      kept. Please check back later.
    </FeaturePaused>
  );
}
