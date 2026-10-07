import { Skeleton, SkeletonGroup } from "@/components/ds/surfaces";

/**
 * Shown at once when a signed-in page is loading, inside the app shell: a heading, a line
 * of text and a few rows. Screen readers hear "Loading" once.
 */
export default function Loading() {
  return (
    <SkeletonGroup label="Loading" className="flex max-w-2xl flex-col gap-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-72 max-w-full" />
      <Skeleton className="mt-2 h-24" />
      <Skeleton className="h-24" />
      <Skeleton className="h-24" />
    </SkeletonGroup>
  );
}
