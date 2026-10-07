"use client";

import { useState } from "react";

import { SegmentedControl, Toast } from "@/components/ds";

/** The segmented filter with working state. */
export function SegmentedDemo() {
  const [value, setValue] = useState<"all" | "requests" | "messages">("all");
  return (
    <div className="flex max-w-sm flex-col gap-2">
      <SegmentedControl
        label="Filter"
        value={value}
        onChange={setValue}
        segments={[
          { value: "all", label: "All" },
          { value: "requests", label: "Requests", count: 2 },
          { value: "messages", label: "Messages", count: 2 },
        ]}
      />
      <p className="text-meta text-muted">Selected: {value}</p>
    </div>
  );
}

/** A dismissible toast, and an error toast. */
export function ToastDemo() {
  const [shown, setShown] = useState(true);
  return (
    <div className="flex max-w-md flex-col gap-3">
      {shown ? (
        <Toast onDismiss={() => setShown(false)}>
          Intro sent. We&apos;ll tell you when they answer.
        </Toast>
      ) : (
        <button
          type="button"
          className="text-meta-lg text-green min-h-11 self-start underline"
          onClick={() => setShown(true)}
        >
          Show the toast again
        </button>
      )}
      <Toast tone="error">We couldn&apos;t send that. Check your connection and try again.</Toast>
    </div>
  );
}
