"use client";

import { useState } from "react";

import { InlineError } from "@/components/ds/fields";
import { browserApi } from "@/lib/api/browser";
import { profileSchema, type Profile } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

/** "Show me in new matches": pausing hides the profile from new matches only. */
export function VisibilityToggle({ initial }: { initial: Profile["visibility"] }) {
  const [visibility, setVisibility] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onChange(checked: boolean) {
    if (saving) return;
    const next = checked ? "matchable" : "paused";
    const previous = visibility;
    // Show the change at once; put it back if the save fails.
    setVisibility(next);
    setSaving(true);
    setError(null);
    try {
      const saved = await browserApi("/me/profile", profileSchema, {
        method: "PATCH",
        body: { visibility: next },
      });
      setVisibility(saved.visibility);
    } catch (caught) {
      setVisibility(previous);
      setError(describeError(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <label className="flex min-h-11 items-start gap-3">
        <input
          type="checkbox"
          role="switch"
          checked={visibility === "matchable"}
          aria-busy={saving}
          onChange={(event) => onChange(event.target.checked)}
          className="accent-green mt-1 size-4 shrink-0"
        />
        <span className="flex flex-col">
          <span className="text-ink font-semibold">Show me in new matches</span>
          <span className="text-meta-lg text-muted">
            {visibility === "matchable"
              ? "People looking for someone like you can be suggested an intro."
              : "Paused: you won't be suggested to anyone new. Existing connections stay."}
          </span>
        </span>
      </label>
      {error ? <InlineError announce>{error}</InlineError> : null}
    </div>
  );
}
