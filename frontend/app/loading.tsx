import { Skeleton, SkeletonGroup } from "@/components/ds/surfaces";

/** Public pages loading (sign-in, the home page): a centred block. */
export default function Loading() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-center gap-4 px-4">
      <SkeletonGroup label="Loading" className="flex flex-col gap-4">
        <Skeleton className="h-6 w-28" />
        <Skeleton className="h-10 w-3/4" />
        <Skeleton className="h-40" />
      </SkeletonGroup>
    </main>
  );
}
