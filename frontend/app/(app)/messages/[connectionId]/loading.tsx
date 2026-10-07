import { Skeleton, SkeletonGroup } from "@/components/ds/surfaces";

/** A chat loading: the header, then message bubbles on alternating sides. */
export default function Loading() {
  return (
    <SkeletonGroup label="Loading the chat" className="flex max-w-2xl flex-col gap-4">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-40" />
      <div className="rounded-panel border-line flex flex-col gap-3 border p-4">
        <Skeleton className="h-10 w-3/5" />
        <Skeleton className="h-10 w-1/2 self-end" />
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-11 w-full" />
      </div>
    </SkeletonGroup>
  );
}
