"use client";

import { useState } from "react";

import { InlineError } from "@/components/ds/fields";
import { browserApi } from "@/lib/api/browser";
import { profileSchema } from "@/lib/api/schemas";
import { describeError } from "@/lib/auth/messages";

/**
 * "Show my Google photo" (ADR 0017): off by default. The picture is the person's Google
 * account picture and nothing else; without one on file the switch can't be turned on.
 */
export function PhotoToggle({
  initial,
  available,
  onSaved,
}: {
  /** The picture shown now, or null when off. */
  initial: string | null;
  /** A Google account picture is on file (the person has signed in with Google). */
  available: boolean;
  /** Told the saved picture, so the page's own avatar follows the switch. */
  onSaved?: (photoUrl: string | null) => void;
}) {
  const [enabled, setEnabled] = useState(initial !== null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const usable = available || enabled;

  async function onChange(checked: boolean) {
    if (saving) return;
    const previous = enabled;
    // Show the change at once; put it back if the save fails.
    setEnabled(checked);
    setSaving(true);
    setError(null);
    try {
      const saved = await browserApi("/me/profile", profileSchema, {
        method: "PATCH",
        body: { show_photo: checked },
      });
      setEnabled(saved.photo_url !== null);
      onSaved?.(saved.photo_url);
    } catch (caught) {
      setEnabled(previous);
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
          checked={enabled}
          disabled={!usable}
          aria-busy={saving}
          onChange={(event) => onChange(event.target.checked)}
          className="accent-green mt-1 size-4 shrink-0"
        />
        <span className="flex flex-col">
          <span className="text-ink font-semibold">Show my Google photo</span>
          <span className="text-meta-lg text-muted">
            {!usable
              ? "Sign in with Google once to use your Google account picture. Until then people see your initials."
              : enabled
                ? "People you're connected with see your Google account picture. Google keeps the picture; we only keep its address."
                : "Off: everyone sees your initials. If you turn it on, only people you're connected with see your Google account picture."}
          </span>
        </span>
      </label>
      {error ? <InlineError announce>{error}</InlineError> : null}
    </div>
  );
}
