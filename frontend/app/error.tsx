"use client";

import { ErrorState } from "@/components/error-state";

/**
 * Last resort for errors outside the signed-in pages, or in the app shell's own layout
 * (for example when the session check fails), where the shell cannot be drawn.
 */
export default function RootError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-lg flex-col justify-center px-4 py-10">
      <ErrorState digest={error.digest} onRetry={retry} />
    </main>
  );
}
