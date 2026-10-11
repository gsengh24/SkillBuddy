"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { CheckIcon } from "@/components/ds/icons";
import { browserApi } from "@/lib/api/browser";
import { introSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

const BUTTON =
  "inline-flex size-11 items-center justify-center rounded-full border disabled:opacity-50";

/** A tick and a cross to answer an incoming intro from the list. Same call as the detail view. */
export function QuickRespond({ introId, onAnswered }: { introId: string; onAnswered: () => void }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function answer(accept: boolean) {
    setBusy(true);
    setError(null);
    try {
      await browserApi(`/intros/${introId}/respond`, introSchema, {
        method: "POST",
        body: { accept },
      });
      onAnswered();
      router.refresh();
    } catch (caught) {
      setError(describeError(caught));
      setBusy(false);
    }
  }

  return (
    <span className="flex shrink-0 items-center gap-1 pl-1">
      <button
        type="button"
        aria-label="Accept intro"
        disabled={busy}
        onClick={() => answer(true)}
        className={`${BUTTON} border-mint text-mint`}
      >
        <CheckIcon />
      </button>
      <button
        type="button"
        aria-label="Decline intro"
        disabled={busy}
        onClick={() => answer(false)}
        className={`${BUTTON} border-danger text-danger`}
      >
        <svg
          aria-hidden
          focusable="false"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          className="size-5"
        >
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
      {error ? (
        <span role="alert" className="sr-only">
          {error}
        </span>
      ) : null}
    </span>
  );
}
