import { FeaturePaused } from "@/components/feature-paused";

/** Pair spaces switched off for everyone on the admin Settings page (A6). */
export function SpacesPaused() {
  return (
    <FeaturePaused title="Pair spaces are paused">
      Pair spaces are switched off for everyone for a while. Your goals and notes are kept. Please
      check back later.
    </FeaturePaused>
  );
}
