"use client";

import { useRouter } from "next/navigation";

import { Button } from "@/components/ds/button";

/** The error state: one sentence, then "Try again" (reloads the page's data). */
export function TryAgain({ message }: { message: string }) {
  const router = useRouter();
  return (
    <div role="alert" className="flex flex-col items-start gap-3 py-4">
      <p className="text-ink">{message}</p>
      <Button variant="outline" onClick={() => router.refresh()}>
        Try again
      </Button>
    </div>
  );
}
