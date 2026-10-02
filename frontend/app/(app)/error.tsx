"use client";

import { ErrorState } from "@/components/error-state";

/** A signed-in page failed to load (usually the API): shown inside the app shell. */
export default function SignedInError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return <ErrorState digest={error.digest} onRetry={retry} />;
}
