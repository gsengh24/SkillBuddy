"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/**
 * Friendly stand-in for a page whose data could not be loaded, used by the error.tsx
 * boundaries. The digest matches the server log line; production error messages are
 * generic, so nothing sensitive is shown.
 */
export function ErrorState({ digest, onRetry }: { digest?: string; onRetry: () => void }) {
  return (
    <Card role="alert" className="flex max-w-lg flex-col items-start gap-4 p-6 sm:p-8">
      <div className="flex flex-col gap-1">
        <h1 className="text-section">Something went wrong</h1>
        <p className="text-muted">We couldn&apos;t load this page. Try again in a moment.</p>
      </div>
      <Button onClick={onRetry}>Try again</Button>
      {digest ? <p className="text-small text-muted font-mono">Reference: {digest}</p> : null}
    </Card>
  );
}
