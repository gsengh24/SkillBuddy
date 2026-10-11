"use client";

import { useRouter } from "next/navigation";

/** The error state on the inbox pane: one sentence, then "Try again" (reloads the page's data). */
export function TryAgain({ message }: { message: string }) {
  const router = useRouter();
  return (
    <div
      role="alert"
      className="text-on-dark-2 grid justify-items-center gap-2.5 px-2.5 py-[30px] text-center text-[14px]"
    >
      <b className="font-display text-on-dark text-[17px] leading-tight font-bold">{message}</b>
      <span>Check your connection and try again.</span>
      <button
        type="button"
        onClick={() => router.refresh()}
        className="border-on-dark-3 text-on-dark hover:bg-on-dark/5 min-h-11 rounded-[10px] border px-4"
      >
        Try again
      </button>
    </div>
  );
}
